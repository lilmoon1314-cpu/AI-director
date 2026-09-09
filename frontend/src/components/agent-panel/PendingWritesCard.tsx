/**
 * 待写入确认卡（F14 轮末统一确认，DESIGN.md §13.2 / OQ-8）：done 事件清单
 * 内联渲染——逐项勾选（默认全选）+ [写入所选][放弃]；approve 由服务端二次
 * 校验落库，成功项移除、失败项保留并挂会话错误态；放弃经 reject 置灰消失。
 */

import { useEffect, useState } from "react";

import type { PendingWriteRead } from "../../api/client";
import { Button } from "../ui/Button";

const KIND_LABELS: Record<PendingWriteRead["kind"], string> = {
  create_entity: "新建实体",
  update_entity: "更新实体",
  create_relation: "新建关系",
  create_memory_doc: "新建文档",
  write_doc_section: "写入段落",
};

export function PendingWritesCard({
  items,
  approving,
  onApprove,
  onReject,
}: {
  items: PendingWriteRead[];
  approving: boolean;
  onApprove: (ids: string[]) => void;
  onReject: (ids: string[]) => void;
}) {
  const [checked, setChecked] = useState<Set<string>>(new Set());

  // 清单变化（新轮登记/项被处理）→ 重置为默认全选
  useEffect(() => {
    setChecked(new Set(items.map((i) => i.id)));
  }, [items]);

  if (items.length === 0) return null;
  const checkedIds = items.filter((i) => checked.has(i.id)).map((i) => i.id);

  const toggle = (id: string) => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div
      className="mx-4 mb-2 rounded-2xl ring-1 ring-black/5 bg-white/80 p-3 shadow-sm backdrop-blur dark:ring-white/10 dark:bg-slate-800/80"
      data-testid="agent-pending-card"
    >
      <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
        待写入（{items.length} 项）——勾选后确认，agent 未擅自落库
      </p>
      <ul className="mt-2 flex flex-col gap-2">
        {items.map((item) => (
          <li
            key={item.id}
            className="rounded-xl bg-slate-50 px-3 py-2 text-sm dark:bg-slate-900/60"
            data-testid="agent-pending-item"
          >
            <label className="flex items-start gap-2 cursor-pointer">
              <input
                type="checkbox"
                className="mt-1"
                checked={checked.has(item.id)}
                onChange={() => toggle(item.id)}
                data-testid="agent-pending-check"
              />
              <span>
                <span className="mr-2 inline-block rounded-full bg-slate-200 px-2 py-0.5 text-xs text-slate-600 dark:bg-slate-700 dark:text-slate-300">
                  {KIND_LABELS[item.kind]}
                </span>
                <span className="text-slate-800 dark:text-slate-200">{item.summary}</span>
              </span>
            </label>
          </li>
        ))}
      </ul>
      <div className="mt-3 flex justify-end gap-2">
        <Button
          variant="ghost"
          className="px-3 py-1 text-xs"
          disabled={approving || checkedIds.length === 0}
          onClick={() => onReject(checkedIds)}
          data-testid="agent-pending-reject"
        >
          放弃所选
        </Button>
        <Button
          className="px-3 py-1 text-xs"
          disabled={approving || checkedIds.length === 0}
          onClick={() => onApprove(checkedIds)}
          data-testid="agent-pending-approve"
        >
          {approving ? "写入中…" : `写入所选（${checkedIds.length}）`}
        </Button>
      </div>
    </div>
  );
}
