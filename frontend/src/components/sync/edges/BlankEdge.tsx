import { memo } from "react";
import { EdgeProps, getBezierPath } from "reactflow";

export const BlankEdge = memo(({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
}: EdgeProps) => {
  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  return (
    <path
      id={id}
      style={style}
      className="react-flow__edge-path stroke-muted-foreground/50"
      d={edgePath}
      markerEnd={markerEnd}
    />
  );
});

BlankEdge.displayName = "BlankEdge"; 