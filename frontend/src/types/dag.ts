import { Node, Edge } from 'reactflow';

export interface DagNode {
  id: string;
  type: 'SOURCE' | 'DESTINATION' | 'ENTITY' | 'TRANSFORMER';
  name: string;
  shortName?: string;
  config?: Record<string, any>;
  sourceId?: string;
  destinationId?: string;
  transformerId?: string;
  entityDefinitionId?: string;
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
    sourceId?: string;
    destinationId?: string;
    transformerId?: string;
    entityDefinitionId?: string;
  };
}

export interface FlowEdge extends Edge {
  type: 'button';
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
      sourceId: node.sourceId,
      destinationId: node.destinationId,
      transformerId: node.transformerId,
      entityDefinitionId: node.entityDefinitionId,
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
    sourceId: node.data.sourceId,
    destinationId: node.data.destinationId,
    transformerId: node.data.transformerId,
    entityDefinitionId: node.data.entityDefinitionId,
  }));

export const toDagEdges = (edges: FlowEdge[]): DagEdge[] =>
  edges.map(edge => ({
    id: edge.id,
    fromNodeId: edge.source,
    toNodeId: edge.target,
  })); 