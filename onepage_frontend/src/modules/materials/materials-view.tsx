"use client";

import { useEffect, useState } from "react";
import { listMaterials, recommendMaterials } from "@/api/materials.api";
import type { MaterialGroup } from "@/types/backend";

export function MaterialsView() {
  const [groups, setGroups] = useState<MaterialGroup[]>([]);
  const [totalMaterials, setTotalMaterials] = useState<number>(0);

  useEffect(() => {
    listMaterials({ type: "sticker" })
      .then((result) => setTotalMaterials(result.pagination.total))
      .catch(() => setTotalMaterials(0));

    recommendMaterials({ style: "healing", emotion: "happy", scene: "sea" })
      .then(setGroups)
      .catch(() =>
        setGroups([
          { material_type: "sticker", items: [] },
          { material_type: "decoration", items: [] },
          { material_type: "template", items: [] }
        ])
      );
  }, []);

  return (
    <section className="mx-auto w-full max-w-[920px]">
      <h1 className="text-2xl font-semibold">素材库</h1>
      <p className="mt-3 text-muted">素材接口已按后端 /materials 与 /materials/recommend 对齐，当前无服务时展示本地占位。</p>
      <p className="mt-1 text-sm text-muted">素材总数（`GET /materials`）：{totalMaterials}</p>
      <div className="mt-8 grid grid-cols-3 gap-5 max-md:grid-cols-1">
        {groups.map((group) => (
          <div key={group.material_type} className="rounded-lg border border-line bg-paper/85 p-5">
            <h2 className="font-semibold">{group.material_type}</h2>
            <div className="mt-4 grid grid-cols-3 gap-3">
              {(group.items.length ? group.items.map((item) => item.id) : Array.from({ length: 6 }, (_, index) => `placeholder-${index}`)).map((id) => (
                <div key={id} className="grid aspect-square place-items-center rounded-lg bg-[#f4eadc] text-xl">
                  ✿
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
