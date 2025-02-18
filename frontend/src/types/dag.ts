import { Node, Edge } from 'reactflow';

export interface DagNode {
  id: string;
  type: 'SOURCE' | 'DESTINATION' | 'ENTITY' | 'TRANSFORMER';
  name: string;
  shortName?: string;
  config?: Record<string, any>;
  connection_id?: string;
  entity_definition_id?: string;
}

export interface DagEdge {
  id: string;
  fromNodeId: string;
  toNodeId: string;
}

export interface DagDefinition {
  id: string;
  name: string;
  description?: string;
  syncId: string;
  nodes: DagNode[];
  edges: DagEdge[];
}

export interface FlowNode extends Node {
  data: {
    name: string;
    shortName?: string;
    config?: Record<string, any>;
    connection_id?: string;
    entity_definition_id?: string;
  };
}

export interface FlowEdge extends Edge {
  type: 'button';
}

// Connection interfaces for source/destination details
export interface Connection {
  id: string;
  name: string;
  integration_type: 'SOURCE' | 'DESTINATION' | 'EMBEDDING_MODEL';
  status: 'active' | 'error' | 'inactive';
  short_name: string;
  organization_id: string;
  created_by_email: string;
  modified_by_email: string;
}

// Conversion utilities
export const toFlowNodes = (nodes: DagNode[]): FlowNode[] => 
  nodes.map(node => ({
    id: node.id,
    type: node.type.toLowerCase(),
    data: {
      name: node.name,
      shortName: node.shortName,
      config: node.config,
      connection_id: node.connection_id,
      entity_definition_id: node.entity_definition_id,
    },
    position: { x: 0, y: 0 }, // Will be set by layout
  }));

export const toFlowEdges = (edges: DagEdge[]): FlowEdge[] =>
  edges.map(edge => ({
    id: edge.id,
    source: edge.fromNodeId,
    target: edge.toNodeId,
    type: 'button',
  }));

export const toDagNodes = (nodes: FlowNode[]): DagNode[] =>
  nodes.map(node => ({
    id: node.id,
    type: node.type.toUpperCase() as DagNode['type'],
    name: node.data.name,
    shortName: node.data.shortName,
    config: node.data.config,
    connection_id: node.data.connection_id,
    entity_definition_id: node.data.entity_definition_id,
  }));

export const toDagEdges = (edges: FlowEdge[]): DagEdge[] =>
  edges.map(edge => ({
    id: edge.id,
    fromNodeId: edge.source,
    toNodeId: edge.target,
  })); 