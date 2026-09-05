/**
 * F08 L1：AssetCardTile 组件单元测试（UF1 等价类：有图/无图、有概述/无概述）。
 * 无图时以类型色占位并显示类型徽标；点击触发 onOpen。
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AssetCardTile } from "../../../src/components/assets/AssetCardTile";

afterEach(cleanup);

describe("AssetCardTile（F08 UF1）", () => {
  it("有图：渲染缩略图与标题/概述（等价类—有图）", () => {
    render(
      <AssetCardTile
        testId="card-1"
        title="愤怒表情"
        description="紧蹙眉头"
        coverUrl="/static/assets/a.png"
        meta="表情参考 · 2 图"
        onOpen={() => {}}
      />,
    );
    const img = screen.getByAltText("愤怒表情");
    expect(img).toHaveProperty("src", "http://localhost:3000/static/assets/a.png");
    expect(screen.getByText("愤怒表情")).toBeTruthy();
    expect(screen.getByText("紧蹙眉头")).toBeTruthy();
    expect(screen.getByText("表情参考 · 2 图")).toBeTruthy();
  });

  it("无图：渲染类型色占位圆与类型徽标（等价类—无图）", () => {
    render(
      <AssetCardTile
        testId="card-2"
        title="沉星湖"
        description=""
        coverUrl={null}
        placeholderType="location"
        onOpen={() => {}}
      />,
    );
    expect(screen.queryByRole("img")).toBeNull();
    expect(screen.getByText("地点")).toBeTruthy();
  });

  it("点击卡片触发 onOpen（行为）", () => {
    const onOpen = vi.fn();
    render(
      <AssetCardTile testId="card-3" title="周兰" description="" coverUrl={null} onOpen={onOpen} />,
    );
    fireEvent.click(screen.getByTestId("card-3"));
    expect(onOpen).toHaveBeenCalledOnce();
  });
});
