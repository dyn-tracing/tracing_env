use indexmap::IndexMap;
use log::trace;
use petgraph::graph::Graph;
use proxy_wasm::traits::Context;
use proxy_wasm::traits::HttpContext;
use proxy_wasm::traits::RootContext;
use proxy_wasm::types::Action;
use proxy_wasm::types::ContextType;
use proxy_wasm::types::LogLevel;
use std::convert::TryFrom;
use std::fmt;


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


fn get_shared_data(trace_id: &str, ctx: &HttpHeaders) -> Option<String> {
    let mut stored_data: String = String::new();
    if let (Some(data), _) = ctx.get_shared_data(&trace_id) {
        // Add a header on the response.
        // TODO: There must be  a nicer way to resolve this
        let stored_data = String::from_utf8_lossy(&data).to_string();
    } else {
        log::warn!("Trace key {:?} not found in shared data.", trace_id);
    }
    return Some(stored_data);
}

fn store_data(data_to_store: String, trace_id: &str, ctx: &HttpHeaders) {
    // Convert to string, then to bytes.
    let stored_data_bytes = Some(data_to_store.as_bytes());

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
            target_graph: Graph::new()
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
        // 1. get shared data
        let shared_data: Option<&str>;
        let shared_data_wrapped = get_shared_data(&trace_id, self);
        if shared_data_wrapped.is_none() {
            shared_data = Some("here are some dummy bytes so we get on with it anyways");
        } else {
            shared_data = Some(shared_data_wrapped.as_ref().unwrap());
        }

        // 2. Put data in headers
        self.set_http_request_header("ferried_data", shared_data);

        // 3. store some more data
        store_data("hello this is a very long string to be stored and I'm going to keep writing and writing until there are a good amount of bytes just like Ferried Data usually is".to_string(),
                   &trace_id, self);

        Ok(())
    }

    fn on_http_request_headers_outbound(&mut self, _num_headers: usize) -> Result<(), String> {
        let trace_id = self
            .get_http_request_header("x-request-id")
            .ok_or_else(|| "Request outbound: x-request-id not found in header!")?;
        // 1. get shared data
        let shared_data: Option<&str>;
        let shared_data_wrapped = get_shared_data(&trace_id, self);
        if shared_data_wrapped.is_none() {
            shared_data = Some("here are some dummy bytes so we get on with it anyways");
        } else {
            shared_data = Some(shared_data_wrapped.as_ref().unwrap());
        }

        // 2. Put data in headers
        self.set_http_request_header("ferried_data", shared_data);

        // 3. store some more data
        store_data("hello this is a very long string to be stored and I'm going to keep writing and writing until there are a good amount of bytes just like Ferried Data usually is".to_string(),
                   &trace_id, self);
        Ok(())
    }

    fn on_http_response_headers_inbound(&mut self, _num_headers: usize) -> Result<(), String> {
        let trace_id = self
            .get_http_response_header("x-request-id")
            .ok_or_else(|| "Response inbound: x-request-id not found in header!")?;
        // 1. get shared data
        let shared_data: Option<&str>;
        let shared_data_wrapped = get_shared_data(&trace_id, self);
        if shared_data_wrapped.is_none() {
            shared_data = Some("here are some dummy bytes so we get on with it anyways");
        } else {
            shared_data = Some(shared_data_wrapped.as_ref().unwrap());
        }

        // 2. Put data in headers
        self.set_http_response_header("ferried_data", shared_data);

        // 3. store some more data
        store_data("hello this is a very long string to be stored and I'm going to keep writing and writing until there are a good amount of bytes just like Ferried Data usually is".to_string(),
                   &trace_id, self);

        Ok(())
    }

    fn on_http_response_headers_outbound(&mut self, _num_headers: usize) -> Result<(), String> {
        let trace_id = self
            .get_http_response_header("x-request-id")
            .ok_or_else(|| "Response outbound: x-request-id not found in header!")?;

        // 1. get shared data
        let shared_data: Option<&str>;
        let shared_data_wrapped = get_shared_data(&trace_id, self);
        if shared_data_wrapped.is_none() {
            shared_data = Some("here are some dummy bytes so we get on with it anyways");
        } else {
            shared_data = Some(shared_data_wrapped.as_ref().unwrap());
        }

        // 2. Put data in headers
        self.set_http_response_header("ferried_data", shared_data);

        // 3. store some more data
        store_data("hello this is a very long string to be stored and I'm going to keep writing and writing until there are a good amount of bytes just like Ferried Data usually is".to_string(),
                   &trace_id, self);
        Ok(())
    }
}
