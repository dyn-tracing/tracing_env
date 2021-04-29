use rpc_lib::rpc::Rpc;
use indexmap::map::IndexMap;
use petgraph::graph::{Graph, NodeIndex};
use petgraph::Incoming;
use utils::graph::graph_utils;
use utils::graph::iso::find_mapping_shamir_decentralized;
use utils::graph::iso::SetSKey;
use serde::{Serialize, Deserialize};
use utils::graph::serde::Property;

extern crate serde_json;

pub type CodeletType = fn(&Filter, &Rpc) -> Option<Rpc>;


// user defined functions:


pub fn create_target_graph() -> Graph<
    (
        std::string::String,
        IndexMap<std::string::String, std::string::String>,
    ),
    (),
> {
     let vertices = vec!(  "a".to_string(), "b".to_string(), "c".to_string(),  );
         let edges = vec!(   ("a".to_string(), "b".to_string() ),   ("b".to_string(), "c".to_string() ),   );
         let mut ids_to_properties: IndexMap<String, IndexMap<String, String>> = IndexMap::new();
         ids_to_properties.insert("a".to_string(), IndexMap::new());
         ids_to_properties.insert("b".to_string(), IndexMap::new());
         ids_to_properties.insert("c".to_string(), IndexMap::new());
         return graph_utils::generate_target_graph(vertices, edges, ids_to_properties);
 

}


#[derive(Clone, Debug)]
pub struct Filter {
    pub whoami: Option<String>,
    pub target_graph: Option<Graph<(String, IndexMap<String, String>), ()>>,
    pub filter_state: IndexMap<String, String>,
    pub envoy_shared_data: IndexMap<String, String>, // trace ID to stored ferried data as string 
    pub collected_properties: Vec<String>, //properties to collect
}

impl Filter {
    #[no_mangle]
    pub fn new() -> *mut Filter {
         Box::into_raw(Box::new(Filter {
            whoami: None,
            target_graph: None,
            filter_state: IndexMap::new(),
            envoy_shared_data: IndexMap::<String, String>::new(),
            collected_properties: vec!( "node.metadata.WORKLOAD_NAME".to_string(),  ),
         }))
    }

    #[no_mangle]
    pub fn new_with_envoy_properties(string_data: IndexMap<String, String>) -> *mut Filter {
        Box::into_raw(Box::new(Filter {
                                   whoami: None,
                                   target_graph: None,
                                   filter_state: string_data,
                                   envoy_shared_data: IndexMap::new(),
                                   collected_properties: vec!("node.metadata.WORKLOAD_NAME".to_string(),  ),
                               }))
     }

    pub fn init_filter(&mut self) {
        if self.whoami.is_none() { self.set_whoami(); assert!(self.whoami.is_some()); }
        if self.target_graph.is_none() { self.target_graph = Some(create_target_graph()); } 
        assert!(self.whoami.is_some());
    }

    pub fn set_whoami(&mut self) {
        if !self.filter_state.contains_key("node.metadata.WORKLOAD_NAME") {
            log::warn!("filter was initialized without envoy properties and thus cannot function");
            return;
        }
        let my_node = self
            .filter_state["node.metadata.WORKLOAD_NAME"].clone();
        self.whoami = Some(my_node);
        assert!(self.whoami.is_some());
    }


    #[no_mangle]
    pub fn execute(&mut self, x: &Rpc) -> Vec<Rpc> {
        self.init_filter();
        assert!(self.whoami.is_some());
        return vec![x.clone()]
    }

}
