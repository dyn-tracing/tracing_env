use proxy_wasm::traits::*;
use proxy_wasm::types::*;
use std::convert::TryFrom;
use std::fmt;

#[no_mangle]
pub fn _start() {
    proxy_wasm::set_log_level(LogLevel::Trace);
    proxy_wasm::set_root_context(|_| -> Box<dyn RootContext> { Box::new(HttpHeadersRoot) });
}

#[repr(i64)]
#[derive(Debug, PartialEq)]
enum TrafficDirection {
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
enum HttpType {
    Unspecified = 0,
    Request = 1,
    Response = 2,
}

struct HttpHeadersRoot;

impl Context for HttpHeadersRoot {}

impl RootContext for HttpHeadersRoot {
    fn get_type(&self) -> Option<ContextType> {
        Some(ContextType::HttpContext)
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
        }))
    }
}

#[allow(dead_code)]
struct HttpHeaders {
    context_id: u32,
    workload_name: String,
}

impl Context for HttpHeaders {}

impl HttpContext for HttpHeaders {
    fn on_http_request_headers(&mut self, _num_headers: usize) -> Action {
        let direction = self.get_traffic_direction();
        if direction == TrafficDirection::Inbound {
            self.on_http_request_headers_inbound();
        } else if direction == TrafficDirection::Outbound {
            self.on_http_request_headers_outbound();
        } else {
            log::error!("Unknown request direction!");
        }

        Action::Continue
    }

    fn on_http_response_headers(&mut self, _num_headers: usize) -> Action {
        let direction = self.get_traffic_direction();
        if direction == TrafficDirection::Inbound {
            self.on_http_response_headers_inbound();
        } else if direction == TrafficDirection::Outbound {
            self.on_http_response_headers_outbound();
        } else {
            log::error!("Unknown request direction!");
        }
        Action::Continue
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

    fn on_http_request_headers_inbound(&mut self) {
    }
    fn on_http_request_headers_outbound(&mut self) {
    }

    fn on_http_response_headers_inbound(&mut self) {
    }

    fn on_http_response_headers_outbound(&mut self) {
    }
}
