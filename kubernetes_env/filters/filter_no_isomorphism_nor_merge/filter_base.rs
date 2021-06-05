use indexmap::IndexMap;
use log::trace;
use petgraph::graph::Graph;
use petgraph::Incoming;
use proxy_wasm::traits::Context;
use proxy_wasm::traits::HttpContext;
use proxy_wasm::traits::RootContext;
use proxy_wasm::types::Action;
use proxy_wasm::types::ContextType;
use proxy_wasm::types::LogLevel;
use std::convert::TryFrom;
use std::fmt;
use std::time::Duration;

use utils::graph::iso::find_mapping_shamir_centralized;
use utils::graph::serde::FerriedData;

// These are generated by the filter
use super::filter::collect_envoy_properties;
use super::filter::create_target_graph;
use super::filter::execute_udfs_and_check_trace_lvl_prop;
use super::filter::get_value_for_storage;

// ---------------------- General Helper Functions ----------------------------

#[repr(i64)]
#[derive(Debug, PartialEq)]
pub enum TrafficDirection {
    Unspecified = 0,
    Inbound = 1,
    Outbound = 2,
}
impl From<i64> for TrafficDirection {
    fn from(orig: i64) -> Self {
        match orig {
            0x1 => return TrafficDirection::Inbound,
            0x2 => return TrafficDirection::Outbound,
            _ => return TrafficDirection::Unspecified,
        };
    }
}

impl fmt::Display for TrafficDirection {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match *self {
            TrafficDirection::Unspecified => write!(f, "unspecified"),
            TrafficDirection::Inbound => write!(f, "inbound"),
            TrafficDirection::Outbound => write!(f, "outbound"),
        }
    }
}

#[repr(u8)]
#[derive(Debug, PartialEq)]
#[allow(dead_code)]
pub enum HttpType {
    Unspecified = 0,
    Request = 1,
    Response = 2,
}

pub fn data_to_str(stored_data: &FerriedData) -> Option<String> {
    let stored_data_str: String;
    match serde_json::to_string(&stored_data) {
        Ok(stored_data_str_) => {
            stored_data_str = stored_data_str_;
        }
        Err(e) => {
            log::error!("Could not translate stored data to json string: {:?}\n", e);
            return None;
        }
    }
    return Some(stored_data_str);
}

pub fn join_str(str_vec: &Vec<&str>) -> String {
    return str_vec.join(".");
}

fn fetch_data_from_headers(ctx: &HttpHeaders, request_type: HttpType) -> FerriedData {
    let data_str_opt: Option<String>;
    if request_type == HttpType::Request {
        data_str_opt = ctx.get_http_request_header("ferried_data");
    } else if request_type == HttpType::Response {
        data_str_opt = ctx.get_http_response_header("ferried_data");
    } else {
        log::error!("Unsupported http type {:?}", request_type);
        return FerriedData::default();
    }
    if let Some(ferried_data_str) = data_str_opt {
        match serde_json::from_str(&ferried_data_str) {
            Ok(fd) => {
                return fd;
            }
            Err(e) => {
                log::error!("Could not translate stored data to json string: {:?}\n", e);
            }
        }
    }
    return FerriedData::default();
}

fn get_shared_data(trace_id: &str, ctx: &HttpHeaders) -> Option<FerriedData> {
    let mut stored_data: FerriedData = FerriedData::default();
    if let (Some(data), _) = ctx.get_shared_data(&trace_id) {
        // Add a header on the response.
        // TODO: There must be  a nicer way to resolve this
        let cast_string = String::from_utf8_lossy(&data).to_string();
        match serde_json::from_str(&cast_string) {
            Ok(d) => {
                stored_data = d;
            }
            Err(e) => {
                log::error!("Could not parse envoy shared data: {:?}\n", e);
                return None;
            }
        }
    } else {
        log::warn!("Trace key {:?} not found in shared data.", trace_id);
    }
    return Some(stored_data);
}

fn store_data(data_to_store: &mut FerriedData, trace_id: &str, ctx: &HttpHeaders) {
    /*
    // Merge with data that is already present.
    let stored_data_opt = get_shared_data(&trace_id, ctx);
    if stored_data_opt.is_some() {
        let stored_data_old = stored_data_opt.unwrap();
        data_to_store.merge(stored_data_old);
    }
    */

    // Convert to string, then to bytes.
    let stored_data_str_opt = data_to_str(&data_to_store);
    if stored_data_str_opt.is_none() {
        // We failed to serialize the shared data.
        // This might lead to wrong results, abort.
        return;
    }
    let stored_data_str = stored_data_str_opt.unwrap();
    let stored_data_bytes = Some(stored_data_str.as_bytes());

    // Update the stored result.
    let store_result = ctx.set_shared_data(&trace_id, stored_data_bytes, None);
    if let Err(ref e) = store_result {
        log::error!(
            "Failed to store key {:?} and value {:?}: {:?}",
            trace_id,
            store_result,
            e
        );
    }
}

// ---------------------------- Filter ------------------------------------

#[no_mangle]
pub fn _start() {
    proxy_wasm::set_log_level(LogLevel::Info);
    proxy_wasm::set_root_context(|_| -> Box<dyn RootContext> {
        Box::new(HttpHeadersRoot {
            target_graph: create_target_graph(),
        })
    });
}

struct HttpHeadersRoot {
    target_graph: Graph<(String, IndexMap<u64, String>), ()>,
}

impl Context for HttpHeadersRoot {}

impl RootContext for HttpHeadersRoot {
    fn get_type(&self) -> Option<ContextType> {
        Some(ContextType::HttpContext)
    }

    fn on_configure(&mut self, _: usize) -> bool {
        true
    }

    fn create_http_context(&self, context_id: u32) -> Option<Box<dyn HttpContext>> {
        let workload_name: String;
        if let Some(workload) = self.get_property(vec!["node", "metadata", "WORKLOAD_NAME"]) {
            match String::from_utf8(workload) {
                Ok(cast_string) => workload_name = cast_string,
                Err(_e) => workload_name = String::new(),
            }
        } else {
            workload_name = String::new();
        }
        Some(Box::new(HttpHeaders {
            context_id,
            workload_name,
            // TODO: This should be a reference instead of a copy
            // Extremely annoying but I can not guarantee a life-time here
            target_graph: self.target_graph.clone(),
        }))
    }
}

pub struct HttpHeaders {
    pub context_id: u32,
    pub workload_name: String,
    pub target_graph: Graph<(String, IndexMap<u64, String>), ()>,
}

impl Context for HttpHeaders {
}

impl HttpContext for HttpHeaders {
    fn on_http_request_headers(&mut self, num_headers: usize) -> Action {
        let direction = self.get_traffic_direction();
        let result: Result<(), String>;
        if direction == TrafficDirection::Inbound {
            result = self.on_http_request_headers_inbound(num_headers);
        } else if direction == TrafficDirection::Outbound {
            result = self.on_http_request_headers_outbound(num_headers);
        } else {
            result = Err("Unknown request direction!".to_string())
        }
        match result {
            Err(e) => log::error!("{:?}", e),
            Ok(_) => (),
        }

        Action::Continue
    }

    fn on_http_response_headers(&mut self, num_headers: usize) -> Action {
        let direction = self.get_traffic_direction();
        let result: Result<(), String>;
        if direction == TrafficDirection::Inbound {
            result = self.on_http_response_headers_inbound(num_headers);
        } else if direction == TrafficDirection::Outbound {
            result = self.on_http_response_headers_outbound(num_headers);
        } else {
            result = Err("Unknown request direction!".to_string())
        }
        match result {
            Err(e) => log::error!("{:?}", e),
            Ok(_) => (),
        }

        Action::Continue
    }

    fn on_log(&mut self) {
        trace!("#{} completed.", self.context_id);
    }
}

impl HttpHeaders {
    // Retrieves the traffic direction from the configuration context.
    fn get_traffic_direction(&self) -> TrafficDirection {
        if let Some(direction_bytes) = self.get_property(vec!["listener_direction"]) {
            let cast_bytes = <[u8; 8]>::try_from(direction_bytes);
            match cast_bytes {
                Ok(byte_array) => return i64::from_ne_bytes(byte_array).into(),
                Err(_e) => return 0i64.into(),
            }
        }
        return 0i64.into();
    }

    fn on_http_request_headers_inbound(&mut self, _num_headers: usize) -> Result<(), String> {
        let trace_id = self
            .get_http_request_header("x-request-id")
            .ok_or_else(|| "Request inbound: x-request-id not found in header!")?;

        // Fetch ferried data
        let mut ferried_data = fetch_data_from_headers(self, HttpType::Request);

        collect_envoy_properties(self, &mut ferried_data)?;

        store_data(&mut ferried_data, &trace_id, self);
        Ok(())
    }

    fn on_http_request_headers_outbound(&mut self, _num_headers: usize) -> Result<(), String> {
        let trace_id = self
            .get_http_request_header("x-request-id")
            .ok_or_else(|| "Request outbound: x-request-id not found in header!")?;
        Ok(())
    }

    fn on_http_response_headers_inbound(&mut self, _num_headers: usize) -> Result<(), String> {
        let trace_id = self
            .get_http_response_header("x-request-id")
            .ok_or_else(|| "Response inbound: x-request-id not found in header!")?;

        // TODO:  Do not really understand the purpose of this yet
        let mut my_indexmap = IndexMap::new();
        my_indexmap.insert(
            0, 
            self.workload_name.clone(),
        );

        // Retrieve the data we have stored
        // We failed to deserialize the shared data.
        // This might lead to wrong results, abort.
        let mut stored_data = get_shared_data(&trace_id, self)
            .ok_or_else(|| format!("Shared data for {:?}", trace_id))?;

        // Figure out what needs to be done here
        // Also handle case where stored data is fresh?
        // TODO: Make this a function? What is this?
        let mut previous_roots = Vec::new();
        for node in stored_data.trace_graph.node_indices() {
            if stored_data
                .trace_graph
                .neighbors_directed(node, Incoming)
                .count()
                == 0
            {
                previous_roots.push(node);
            }
        }
        let me = stored_data
            .trace_graph
            .add_node((self.workload_name.clone(), my_indexmap));

        for previous_root in previous_roots {
            stored_data.trace_graph.add_edge(me, previous_root, ());
        }
        stored_data.assign_properties();

        // If we are not the root id, return
        // TODO:: Add some diagnostic when we are not the root node
        let trace_prop_sat = execute_udfs_and_check_trace_lvl_prop(self, &mut stored_data);

        if self.workload_name == "productpage-v1" && trace_prop_sat {
            // 2. calculate UDFs and store result, and check trace level properties

            /*
            if let Some(mapping) =
                find_mapping_shamir_centralized(&stored_data.trace_graph, &self.target_graph)
            {
                let value = get_value_for_storage(&self.target_graph, &mapping, &stored_data)
                    .ok_or_else(|| "Failed to retrieve value from storage.")?;
                let call_result = self.dispatch_http_call(
                    "storage-upstream",
                    vec![
                        (":method", "GET"),
                        (":path", "/store"),
                        (":authority", "storage-upstream"),
                        ("key", &trace_id),
                        ("value", &value),
                        ("x-request-id", &trace_id),
                    ],
                    None,
                    vec![],
                    Duration::from_secs(5),
                );
                match call_result {
                    Ok(_ok) => {}
                    Err(e) => log::error!("Failed to make a call to storage {:?}", e),
                }
            } else {
                log::error!("Mapping not found");
            }
            */
        }
        

        // Now store the data again after we have computed over it
        // We failed to serialize the shared data.
        // This might lead to wrong results, abort.
        let stored_data_str =
            data_to_str(&stored_data).ok_or_else(|| "Failed to convert data to string.")?;
        // Set the header
        self.set_http_response_header("ferried_data", Some(&stored_data_str));
        Ok(())
    }

    fn on_http_response_headers_outbound(&mut self, _num_headers: usize) -> Result<(), String> {
        let trace_id = self
            .get_http_response_header("x-request-id")
            .ok_or_else(|| "Response outbound: x-request-id not found in header!")?;
        // Fetch ferried data
        let mut ferried_data = fetch_data_from_headers(self, HttpType::Response);

        store_data(&mut ferried_data, &trace_id, self);
        Ok(())
    }
}
