"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronRight, FileText } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import type { TreeNode } from "@/lib/types";
import { cn } from "@/lib/utils";

// ─── Single tree node row (recursive) ────────────────────────────────────────

interface TreeNodeRowProps {
  node: TreeNode;
  depth: number;
  expandedNodes: Set<string>;
  referencedNodeIds: Set<string>;
  hoveredNodeId: string | null;
  onToggle: (id: string) => void;
  onDoubleClick: (node: TreeNode) => void;
  onHover: (id: string | null) => void;
}

function TreeNodeRow({
  node,
  depth,
  expandedNodes,
  referencedNodeIds,
  hoveredNodeId,
  onToggle,
  onDoubleClick,
  onHover,
}: TreeNodeRowProps) {
  const hasChildren = node.children.length > 0;
  const isExpanded = expandedNodes.has(node.id);
  const isReferenced = referencedNodeIds.has(node.id);
  const isHovered = hoveredNodeId === node.id;

  return (
    <>
      <div
        data-node-id={node.id}
        style={{ paddingLeft: `${8 + depth * 14}px` }}
        className={cn(
          "group flex items-center gap-1.5 pr-3 py-1.5 rounded-md cursor-pointer select-none transition-colors duration-100",
          isReferenced
            ? "bg-[#7C3AED]/10 border-l-2 border-[#7C3AED] text-[#7C3AED]"
            : "hover:bg-accent text-foreground",
          isHovered && !isReferenced && "bg-[#7C3AED]/5"
        )}
        onClick={() => hasChildren && onToggle(node.id)}
        onDoubleClick={() => onDoubleClick(node)}
        onMouseEnter={() => onHover(node.id)}
        onMouseLeave={() => onHover(null)}
        role="treeitem"
        aria-expanded={hasChildren ? isExpanded : undefined}
        aria-selected={isReferenced}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter") hasChildren && onToggle(node.id);
          if (e.key === " ") { e.preventDefault(); onDoubleClick(node); }
        }}
      >
        {/* Expand chevron */}
        <span className="shrink-0 w-4 flex items-center justify-center">
          {hasChildren ? (
            <ChevronRight
              className={cn(
                "h-3.5 w-3.5 text-muted-foreground transition-transform duration-150",
                isExpanded && "rotate-90"
              )}
            />
          ) : (
            <FileText className="h-3 w-3 text-muted-foreground/40" />
          )}
        </span>

        {/* Title */}
        <span
          className={cn(
            "flex-1 min-w-0 text-[13px] leading-snug truncate",
            isReferenced ? "font-medium" : "font-normal"
          )}
          title={node.title}
        >
          {node.title}
        </span>

        {/* Page range */}
        <span className="shrink-0 text-[10px] font-mono text-muted-foreground/60 whitespace-nowrap ml-1">
          {node.page_start === node.page_end
            ? `p.${node.page_start}`
            : `p.${node.page_start}–${node.page_end}`}
        </span>
      </div>

      {/* Children */}
      {isExpanded && hasChildren && (
        <div role="group">
          {node.children.map((child) => (
            <TreeNodeRow
              key={child.id}
              node={child}
              depth={depth + 1}
              expandedNodes={expandedNodes}
              referencedNodeIds={referencedNodeIds}
              hoveredNodeId={hoveredNodeId}
              onToggle={onToggle}
              onDoubleClick={onDoubleClick}
              onHover={onHover}
            />
          ))}
        </div>
      )}
    </>
  );
}

// ─── TreeView ─────────────────────────────────────────────────────────────────

interface TreeViewProps {
  nodes: TreeNode[];
  isLoading: boolean;
  referencedNodeIds: Set<string>;
  hoveredNodeId: string | null;
  onNodeDoubleClick: (node: TreeNode) => void;
  onNodeHover: (id: string | null) => void;
  scrollRef: React.RefObject<HTMLDivElement>;
}

export function TreeView({
  nodes,
  isLoading,
  referencedNodeIds,
  hoveredNodeId,
  onNodeDoubleClick,
  onNodeHover,
  scrollRef,
}: TreeViewProps) {
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());

  const toggle = useCallback((id: string) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  // Auto-expand ancestors of referenced nodes when referenced set changes
  useEffect(() => {
    if (referencedNodeIds.size === 0) return;

    setExpandedNodes((prev) => {
      const next = new Set(prev);

      const expand = (nodeList: TreeNode[]): boolean => {
        let found = false;
        for (const node of nodeList) {
          const childFound =
            node.children.length > 0 && expand(node.children);
          if (referencedNodeIds.has(node.id) || childFound) {
            found = true;
            if (childFound) next.add(node.id); // expand this ancestor
          }
        }
        return found;
      };

      expand(nodes);
      return next;
    });
  }, [referencedNodeIds, nodes]);

  // Scroll to first referenced node after expansion renders
  useEffect(() => {
    if (referencedNodeIds.size === 0) return;
    const raf = requestAnimationFrame(() => {
      const firstId = [...referencedNodeIds][0];
      const el = scrollRef.current?.querySelector(
        `[data-node-id="${firstId}"]`
      );
      el?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
    return () => cancelAnimationFrame(raf);
  }, [referencedNodeIds, expandedNodes, scrollRef]);

  if (isLoading) {
    return (
      <div className="p-3 space-y-1.5">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton
            key={i}
            className="h-7 rounded-md"
            style={{ width: `${70 + Math.random() * 25}%`, marginLeft: `${(i % 3) * 14}px` }}
          />
        ))}
      </div>
    );
  }

  if (nodes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-12 text-center px-4">
        <FileText className="h-8 w-8 text-muted-foreground/40" />
        <p className="text-sm text-muted-foreground">
          No tree structure found for this document.
        </p>
      </div>
    );
  }

  return (
    <div
      ref={scrollRef}
      className="h-full overflow-y-auto scrollbar-thin p-2"
      role="tree"
      aria-label="Document structure"
    >
      {nodes.map((node) => (
        <TreeNodeRow
          key={node.id}
          node={node}
          depth={0}
          expandedNodes={expandedNodes}
          referencedNodeIds={referencedNodeIds}
          hoveredNodeId={hoveredNodeId}
          onToggle={toggle}
          onDoubleClick={onNodeDoubleClick}
          onHover={onNodeHover}
        />
      ))}
    </div>
  );
}
