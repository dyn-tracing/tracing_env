use log::trace;
use proxy_wasm::traits::Context;
use proxy_wasm::traits::HttpContext;
use proxy_wasm::traits::RootContext;
use proxy_wasm::types::Action;
use proxy_wasm::types::ContextType;
use proxy_wasm::types::LogLevel;
use std::convert::TryFrom;
use std::fmt;
use serde::{Serialize, Deserialize};


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

// ---------------------------- Filter ------------------------------------

#[no_mangle]
pub fn _start() {
    proxy_wasm::set_log_level(LogLevel::Info);
    proxy_wasm::set_root_context(|_| -> Box<dyn RootContext> {
        Box::new(HttpHeadersRoot {
        })
    });
}

struct HttpHeadersRoot {
}

impl Context for HttpHeadersRoot {}

impl RootContext for HttpHeadersRoot {
    fn get_type(&self) -> Option<ContextType> {
        Some(ContextType::HttpContext)
    }

    fn on_configure(&mut self, _: usize) -> bool {
        // TODO: put empty structs in storage for UDFs
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
        let mut ctx = HttpHeaders {
            context_id, workload_name
        };
        

        Some(Box::new(ctx))
    }
}

pub struct HttpHeaders {
    pub context_id: u32,
    pub workload_name: String,
}

impl Context for HttpHeaders {
    /// Process the callback from any http calls the filter makes for debugging.
    /// This is usually from storage.
    /// TODO: This is not working reliably yet. Needs some investigating.
    fn on_http_call_response(
        &mut self,
        _token_id: u32,
        _num_headers: usize,
        body_size: usize,
        _: usize,
    ) {
        log::warn!("Received response from storage");
        if let Some(body) = self.get_http_call_response_body(0, body_size) {
            log::warn!("Storage body: {:?}", body);
        }
        for (name, value) in &self.get_http_response_headers() {
            log::warn!("Storage Header - {:?}: {:?}", name, value);
        }
    }
}

impl HttpContext for HttpHeaders {
    fn on_http_request_headers(&mut self, num_headers: usize) -> Action {
        let direction = self.get_traffic_direction();
        log::warn!(
            "{}: Request Header Direction {}",
            self.workload_name,
            direction
        );
        self.print_headers(HttpType::Request);
        if direction == TrafficDirection::Inbound {
            self.on_http_request_headers_inbound(num_headers);
        } else if direction == TrafficDirection::Outbound {
            self.on_http_request_headers_outbound(num_headers);
        } else {
            log::error!("Unknown request direction!");
        }
        Action::Continue
    }

    fn on_http_response_headers(&mut self, num_headers: usize) -> Action {
        let direction = self.get_traffic_direction();
        log::warn!(
            "{}: Response Header Direction {}",
            self.workload_name,
            direction
        );
        self.print_headers(HttpType::Response);

        if direction == TrafficDirection::Inbound {
            self.on_http_response_headers_inbound(num_headers);
        } else if direction == TrafficDirection::Outbound {
            self.on_http_response_headers_outbound(num_headers);
        } else {
            log::error!("Unknown request direction!");
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

    fn print_headers(&self, request_type: HttpType) {
        if request_type == HttpType::Request {
            for (name, value) in &self.get_http_request_headers() {
                log::warn!("#{} -> {}: {}", self.context_id, name, value);
            }
        } else if request_type == HttpType::Response {
            for (name, value) in &self.get_http_response_headers() {
                log::warn!("#{} -> {}: {}", self.context_id, name, value);
            }
        } else {
            log::error!("Unsupported http type {:?}", request_type);
        }
    }

    fn on_http_request_headers_inbound(&mut self, _num_headers: usize) {
        // Get the trace ID
        let trace_id: String;
        if let Some(trace_id_) = self.get_http_request_header("x-request-id") {
            trace_id = trace_id_;
            log::warn!("Request inbound: Using trace id {}!", trace_id);
        } else {
            log::error!("Request inbound: x-request-id not found in header!",);
            return;
        }

        // Perform the aggregation function FIXME?  Only works for one aggregation function, not yet sure if we want to support multiple
        

    }

    fn on_http_request_headers_outbound(&mut self, _num_headers: usize) {
        let trace_id: String;
        if let Some(trace_id_) = self.get_http_request_header("x-request-id") {
            trace_id = trace_id_;
            log::warn!("Request outbound: Using trace id {}!", trace_id);
        } else {
            log::error!("Request outbound: x-request-id not found in header!",);
            return;
        }
    }

    fn on_http_response_headers_inbound(&mut self, _num_headers: usize) {
        let trace_id: String;
        if let Some(trace_id_) = self.get_http_response_header("x-request-id") {
            trace_id = trace_id_;
            log::warn!("Response inbound: Using trace id {}!", trace_id);
        } else {
            log::error!("Response inbound: x-request-id not found in header!",);
            return;
        }
    }

    fn on_http_response_headers_outbound(&mut self, _num_headers: usize) {
        let trace_id: String;
        if let Some(trace_id_) = self.get_http_response_header("x-request-id") {
            trace_id = trace_id_;
            log::warn!("Response outbound: Using trace id {}!", trace_id);
        } else {
            log::error!("Response outbound: x-request-id not found in header!",);
            return;
        }
    }
}
