// ---------------------- Generated Functions ----------------------------

use super::filter_base::HttpHeaders;
use proxy_wasm::traits::Context;
use indexmap::IndexMap;
use petgraph::graph::{Graph, NodeIndex};
use utils::graph::graph_utils::generate_target_graph;
use utils::graph::graph_utils::get_node_with_id;
use utils::graph::serde::FerriedData;
use utils::graph::serde::Property;

// insert UDFs here


pub fn create_target_graph() -> Graph<
    (
        std::string::String,
        IndexMap<u64, std::string::String>,
    ),
    (),
> {
     let vertices = vec!( "a".to_string(),"b".to_string(),"c".to_string(), );
        let edges = vec!(  ("a".to_string(), "b".to_string() ),  ("b".to_string(), "c".to_string() ),  );
        let mut ids_to_properties: IndexMap<String, IndexMap<u64, String>> = IndexMap::new();
        ids_to_properties.insert("a".to_string(), IndexMap::new());
        ids_to_properties.insert("b".to_string(), IndexMap::new());
        ids_to_properties.insert("c".to_string(), IndexMap::new());
        let mut c_hashmap = ids_to_properties.get_mut("c").unwrap();
        c_hashmap.insert(0, "ratings-v1".to_string());
        return generate_target_graph(vertices, edges, ids_to_properties);

}

pub fn collect_envoy_properties(
    http_headers: &HttpHeaders,
    fd: &mut FerriedData,
) -> Result<(), String> {
    
             let property = http_headers
                            .get_property(vec!["node", "metadata", "WORKLOAD_NAME", ].to_vec())
                            .ok_or_else(|| format!("Failed to retrieve property node.metadata.WORKLOAD_NAME."))?;
            
    
                     match std::str::from_utf8(&property) {
                        Ok(property_str_) => {
                            fd.unassigned_properties.insert(Property::new(
                                http_headers.workload_name.to_string(), 
                                0,
                                property_str_.to_string()
                            ));
                        }
                        Err(e) => { return Err(e.to_string()); }
                    };
                
    
             let property = http_headers
                            .get_property(vec!["node", "metadata", "WORKLOAD_NAME", ].to_vec())
                            .ok_or_else(|| format!("Failed to retrieve property node.metadata.WORKLOAD_NAME."))?;
            
    
                     match std::str::from_utf8(&property) {
                        Ok(property_str_) => {
                            fd.unassigned_properties.insert(Property::new(
                                http_headers.workload_name.to_string(), 
                                0,
                                property_str_.to_string()
                            ));
                        }
                        Err(e) => { return Err(e.to_string()); }
                    };
                
    
    return Ok(());
}

pub fn execute_udfs_and_check_trace_lvl_prop(http_headers: &HttpHeaders, fd: &mut FerriedData) -> bool {
    // Empty for this query, but in general, will be useful
    
    let root_id = "productpage-v1";
    
            if &http_headers.workload_name == root_id {        let mut trace_prop_str : String;
       }
    return true;
}

pub fn get_value_for_storage(
    target_graph: &Graph<
        (
            std::string::String,
            IndexMap<u64, std::string::String>,
        ),
        (),
    >,
    mapping: &Vec<(NodeIndex, NodeIndex)>,
    stored_data: &FerriedData,
) -> Option<String> {
    let value: String;
    let node_ptr = get_node_with_id(target_graph, "a");
        if node_ptr.is_none() {
           log::error!("Node a not found");
                return None;
        }
        let mut trace_node_idx_opt = None;
        for map in mapping {
            if target_graph.node_weight(map.0).unwrap().0 == "a" {
                trace_node_idx_opt = Some(map.1);
                break;
            }
        }
        if trace_node_idx_opt.is_none() {
            log::error!("Node index a not found.");
            // we have not yet collected the return property or have a mapping error
            return None;
        }
        let trace_node_idx = trace_node_idx_opt.unwrap();
        if !&stored_data
            .trace_graph
            .node_weight(trace_node_idx)
            .unwrap()
            .1
            .contains_key(&0)
        {
            // we have not yet collected the return property
            log::error!("Missing return property node.metadata.WORKLOAD_NAME");
            return None;
        }
        let ret = &stored_data.trace_graph.node_weight(trace_node_idx).unwrap().1[ 0 ];

        value = ret.to_string();


    return Some(value);
}


