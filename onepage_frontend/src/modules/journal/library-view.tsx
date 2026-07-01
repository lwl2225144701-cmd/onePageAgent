"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronLeft, ChevronRight, Plus, X } from "lucide-react";
import { getJournal, listJournals } from "@/api/journals.api";
import { getPage } from "@/api/pages.api";
import { useJournalStore } from "@/stores/journal-store";
import type { PageResponse } from "@/types/backend";

type PageBrief = Pick<PageResponse, "id" | "title" | "thumbnail_url" | "mood" | "page_date" | "created_at">;

type BookYear = {
  year: string;
  title: string;
  tone: "cream" | "rose" | "sage";
  plant: "sprig" | "flower" | "leaf";
};

type ShelfItem =
  | { kind: "book"; book: BookYear; pageCount?: number; quiet?: boolean }
  | { kind: "new" };

const shelfBooks: BookYear[] = [
  { year: "2024", title: "灵感册", tone: "cream", plant: "sprig" },
  { year: "2025", title: "新时光", tone: "rose", plant: "flower" },
  { year: "2026", title: "未来页", tone: "sage", plant: "leaf" },
];

const historyBooks: BookYear[] = [
  { year: "2023", title: "旧时光", tone: "cream", plant: "sprig" },
  { year: "2022", title: "月拾光", tone: "sage", plant: "leaf" },
];

const bookPalettes = {
  cream: {
    cover: "#EFE3CC",
    spine: "#DEC59F",
    edge: "#F3E7D0",
    shadow: "#B98F5F",
    text: "#8A5B2F",
    plant: "#B99052",
    ribbon: "#D8B77D",
  },
  rose: {
    cover: "#DFAF99",
    spine: "#C88F78",
    edge: "#F4CEBE",
    shadow: "#A96F58",
    text: "#704633",
    plant: "#9A604D",
    ribbon: "#D69A85",
  },
  sage: {
    cover: "#B7BEA3",
    spine: "#929C80",
    edge: "#D4D8C4",
    shadow: "#70785F",
    text: "#596246",
    plant: "#64734F",
    ribbon: "#91A083",
  },
} satisfies Record<BookYear["tone"], Record<string, string>>;

const pageStyle = {
  backgroundColor: "#F8F5EE",
  backgroundImage:
    "radial-gradient(circle at 72% 11%, rgba(255,255,255,0.90), transparent 22%), radial-gradient(circle at 18% 10%, rgba(255,251,242,0.88), transparent 28%), linear-gradient(180deg, #FBF8F2 0%, #F8F3EA 48%, #F5EDE2 100%)",
} satisfies React.CSSProperties;

const shelfFrameStyle = {
  backgroundColor: "#E9D7BB",
  backgroundImage:
    "linear-gradient(90deg, rgba(173,119,61,0.16), rgba(255,255,255,0.58) 10%, rgba(255,255,255,0.18) 18%, transparent 52%, rgba(142,91,44,0.14)), repeating-linear-gradient(96deg, rgba(139,88,40,0.08) 0 1px, transparent 1px 18px), linear-gradient(180deg, #F6DEB8 0%, #E9C393 47%, #D3A06B 100%)",
  boxShadow:
    "0 12px 24px rgba(116,74,36,0.11), inset 0 1px 0 rgba(255,255,255,0.48), inset 0 -8px 15px rgba(127,77,35,0.14)",
} satisfies React.CSSProperties;

const shelfInteriorStyle = {
  backgroundColor: "#E6C89F",
  backgroundImage:
    "radial-gradient(ellipse at 64% 62%, rgba(255,238,198,0.52), rgba(255,232,182,0.18) 22%, transparent 43%), linear-gradient(90deg, rgba(115,72,35,0.20), rgba(255,248,222,0.24) 18%, transparent 42%, rgba(95,59,28,0.10)), repeating-linear-gradient(90deg, rgba(117,73,33,0.10) 0 1px, transparent 1px 34px), repeating-linear-gradient(92deg, transparent 0 72px, rgba(255,255,255,0.12) 73px 75px, transparent 76px 148px), linear-gradient(180deg, #E9C89A 0%, #DFB579 54%, #D2A06B 100%)",
  boxShadow: "inset 0 16px 30px rgba(87,53,25,0.30), inset 0 0 0 1px rgba(255,255,255,0.28)",
} satisfies React.CSSProperties;

export function LibraryView({ onCreate, onOpenPage }: { onCreate: () => void; onOpenPage: (page: PageResponse) => void }) {
  const { journals, localPages, setJournals } = useJournalStore();
  const [selectedBook, setSelectedBook] = useState<BookYear | undefined>();
  const [selectedJournalId, setSelectedJournalId] = useState<string | undefined>();
  const [selectedPages, setSelectedPages] = useState<PageBrief[]>([]);
  const [pagesLoading, setPagesLoading] = useState(false);

  useEffect(() => {
    listJournals()
      .then((result) => setJournals(result.data))
      .catch(() => setJournals([]));
  }, [setJournals]);

  const pageCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    journals.forEach((journal) => {
      const year = journalYear(journal.name, journal.settings);
      if (year) counts[year] = (counts[year] ?? 0) + journal.page_count;
    });
    localPages.forEach((page) => {
      if (page.user_id !== "local") return;
      const year = pageYear(page);
      if (year) counts[year] = (counts[year] ?? 0) + 1;
    });
    return counts;
  }, [journals, localPages]);

  async function openBook(book: BookYear) {
    setSelectedBook(book);
    setPagesLoading(true);
    const journal =
      journals.find((item) => item.name === `${book.year} 手账本`) ??
      journals.find((item) => journalYear(item.name, item.settings) === book.year);
    setSelectedJournalId(journal?.id);
    const localForYear = localPages.filter((page) => pageYear(page) === book.year);
    if (!journal) {
      setSelectedPages(mergePages([], localForYear));
      setPagesLoading(false);
      return;
    }
    const detail = await getJournal(journal.id).catch(() => undefined);
    setSelectedPages(mergePages((detail?.pages as PageBrief[] | undefined) ?? [], localForYear));
    setPagesLoading(false);
  }

  async function openSavedPage(page: PageBrief) {
    const localPage = localPages.find((item) => item.id === page.id && item.layout_json);
    if (localPage) {
      onOpenPage(localPage);
      return;
    }
    const detail = await getPage(page.id).catch(() => undefined);
    if (detail) onOpenPage(detail);
  }

  return (
    <section className="grid min-h-[calc(100dvh-112px)] place-items-center max-md:items-stretch">
      <div
        className="library-page relative flex min-h-[690px] w-full max-w-[360px] flex-col overflow-hidden rounded-[20px] border border-line px-3 pb-[clamp(10px,2dvh,14px)] pt-0 shadow-journal max-md:min-h-[calc(100dvh-128px)] max-md:max-w-none"
        style={pageStyle}
      >
        <LibrarySceneStyle />
        <LibraryHeader />
        <PaperTear />
        <div className="relative z-10 mt-1 flex min-h-0 flex-1">
          <WoodCabinet pageCounts={pageCounts} onCreate={onCreate} onOpenBook={openBook} />
        </div>
        {selectedBook ? (
          <BookPagesPanel
            book={selectedBook}
            journalId={selectedJournalId}
            pages={selectedPages}
            loading={pagesLoading}
            onClose={() => setSelectedBook(undefined)}
            onCreate={onCreate}
            onOpenPage={openSavedPage}
          />
        ) : null}
      </div>
    </section>
  );
}

function LibraryHeader() {
  return (
    <header className="relative z-30 flex h-[84px] items-center justify-between px-2 pt-4">
      <button className="grid h-11 w-11 place-items-center rounded-full text-[#4F3D2C] transition hover:bg-[#efe4d4]/70" title="返回">
        <ChevronLeft size={24} strokeWidth={2.1} />
      </button>
      <h1 className="font-song pointer-events-none absolute left-1/2 top-[35px] -translate-x-1/2 text-[24px] font-semibold leading-none tracking-[0.06em] text-[#4F3D2C]">
        我的手账本
      </h1>
      <button className="grid h-11 w-11 place-items-center rounded-full text-[#4F3D2C] transition hover:bg-[#efe4d4]/70" title="切换视图">
        <ChevronDown size={24} strokeWidth={2.1} />
      </button>
    </header>
  );
}

function PaperTear() {
  return (
    <div className="pointer-events-none relative z-20 -mx-3 -mt-[2px] h-[36px]">
      <div className="paper-shadow absolute inset-x-0 top-[25px] h-7" />
      <div className="paper-rip absolute inset-x-0 top-0 h-[32px] bg-[#FBF8F2]" />
      <div className="absolute right-[38px] top-[1px] h-[13px] w-[40px] rotate-[8deg] rounded-[3px] bg-[#DEB985]/20 shadow-[0_1px_5px_rgba(142,91,44,0.06)]" />
      <div className="absolute right-[56px] top-[-16px] h-[34px] w-[38px] opacity-50">
        <TinyDriedStem className="left-[14px] top-[8px] h-8 rotate-[-22deg]" />
        <TinyDriedStem className="left-[22px] top-[7px] h-7 rotate-[8deg]" />
        <TinyDriedStem className="left-[28px] top-[12px] h-6 rotate-[31deg]" />
      </div>
    </div>
  );
}

function TinyDriedStem({ className }: { className: string }) {
  return (
    <div className={`absolute w-px origin-bottom bg-[#C49A67] ${className}`}>
      <span className="absolute -left-[4px] -top-[1px] h-[6px] w-[6px] rounded-full bg-[#E7C59B]" />
      <span className="absolute left-[3px] top-[7px] h-[5px] w-[5px] rounded-full bg-[#EBD2AE]" />
    </div>
  );
}

function WoodCabinet({
  pageCounts,
  onCreate,
  onOpenBook,
}: {
  pageCounts: Record<string, number>;
  onCreate: () => void;
  onOpenBook: (book: BookYear) => void;
}) {
  const bookItems: ShelfItem[] = [
    ...shelfBooks.map((book) => ({ kind: "book" as const, book, pageCount: pageCounts[book.year] ?? 0 })),
    ...historyBooks.map((book) => ({ kind: "book" as const, book, pageCount: pageCounts[book.year] ?? 0, quiet: true })),
    { kind: "new" },
  ];
  const shelfRows = chunkShelfItems(bookItems, 3);

  return (
    <div className="relative mx-auto flex min-h-0 w-full max-w-[366px] flex-1 overflow-visible pb-[2px]">
      <div className="relative min-h-0 flex-1 overflow-hidden rounded-t-[32px] rounded-b-[10px] p-[10px]" style={shelfFrameStyle}>
        <div className="relative h-full overflow-hidden rounded-t-[24px] rounded-b-[4px]" style={shelfInteriorStyle}>
          <NaturalLight />
          <div className="library-shelf-scroll relative z-20 h-full overflow-y-auto overscroll-contain px-[18px] pb-[58px] pt-0">
            <div
              className="library-shelf-stack grid h-full gap-0"
              style={{ gridTemplateRows: `repeat(${shelfRows.length}, minmax(204px, 1fr))` }}
            >
              {shelfRows.map((row, index) => (
                <ShelfLayer key={index} items={row} layerIndex={index} onCreate={onCreate} onOpenBook={onOpenBook} />
              ))}
            </div>
          </div>
          <Drawer />
          <DeskDecoration />
        </div>
      </div>
    </div>
  );
}

function ShelfLayer({
  items,
  layerIndex,
  onCreate,
  onOpenBook,
}: {
  items: ShelfItem[];
  layerIndex: number;
  onCreate: () => void;
  onOpenBook: (book: BookYear) => void;
}) {
  const booksBottom = layerIndex === 0 ? "bottom-[70px]" : "bottom-[58px]";
  const boardBottom = layerIndex === 0 ? 44 : 32;

  return (
    <div className="relative min-h-[204px]">
      <div className={`absolute ${booksBottom} left-0 right-0 z-30 grid grid-cols-3 items-end gap-[18px]`}>
        {items.map((item, index) => (
          <ShelfItemView key={`${item.kind}-${index}`} item={item} onCreate={onCreate} onOpenBook={onOpenBook} />
        ))}
      </div>
      <LayerShelfBoard bottom={boardBottom} />
    </div>
  );
}

function ShelfItemView({
  item,
  onCreate,
  onOpenBook,
}: {
  item: ShelfItem;
  onCreate: () => void;
  onOpenBook: (book: BookYear) => void;
}) {
  if (item.kind === "new") {
    return (
      <div className="-translate-x-1.5">
        <NewBookSlot onCreate={onCreate} />
      </div>
    );
  }

  return (
    <div className={item.quiet ? "opacity-75" : undefined}>
      <JournalBook book={item.book} pageCount={item.pageCount ?? 0} onOpen={() => onOpenBook(item.book)} />
    </div>
  );
}

function LayerShelfBoard({ bottom }: { bottom: number }) {
  return (
    <>
      <div className="shelf-board absolute left-[-18px] right-[-18px] z-[12] h-[18px] bg-[#EEC996]" style={{ bottom }} />
      <div className="absolute left-[-18px] right-[-18px] z-[11] h-[17px] bg-[#B97A43] shadow-[inset_0_6px_12px_rgba(82,48,22,0.24),0_8px_18px_rgba(82,48,22,0.18)]" style={{ bottom: bottom - 17 }} />
    </>
  );
}

function Drawer() {
  return (
    <div className="absolute bottom-0 left-0 right-0 z-[13] h-[44px] bg-[linear-gradient(180deg,#E1B984_0%,#D5A06A_100%)] shadow-[inset_0_6px_11px_rgba(106,66,31,0.055),0_-1px_0_rgba(255,255,255,0.20)]">
      <div className="absolute inset-x-[18px] top-[12px] h-px bg-[#8F5D2F]/12" />
      <div className="absolute inset-x-[24px] top-[30px] h-px bg-white/14" />
      <div className="absolute left-1/2 top-[24px] h-[10px] w-[10px] -translate-x-1/2 rounded-full border border-[#8C6031]/20 bg-[radial-gradient(circle_at_35%_28%,#DDB978,#9D713C_62%,#7B562C)] shadow-[0_2px_4px_rgba(83,51,24,0.06)]" />
    </div>
  );
}

function NaturalLight() {
  return (
    <div className="pointer-events-none absolute inset-0 z-[5]">
      <div className="absolute right-[78px] top-[278px] h-[148px] w-[114px] rotate-[14deg] rounded-[48%] bg-[radial-gradient(ellipse_at_center,rgba(255,246,214,0.30),rgba(255,235,182,0.13)_36%,transparent_72%)] blur-[2px]" />
      <div className="absolute right-[92px] top-[304px] h-[110px] w-[70px] rotate-[18deg] bg-[linear-gradient(106deg,transparent_0_24%,rgba(255,255,235,0.12)_25%_33%,transparent_34%_52%,rgba(255,255,235,0.08)_53%_62%,transparent_63%)] blur-[1px]" />
      <div className="absolute right-[46px] top-[332px] h-[100px] w-[140px] rotate-[-8deg] bg-[radial-gradient(ellipse_at_center,rgba(255,249,224,0.10),transparent_68%)]" />
    </div>
  );
}

function JournalBook({ book, pageCount, onOpen }: { book: BookYear; pageCount: number; onOpen: () => void }) {
  const palette = bookPalettes[book.tone];

  return (
    <button
      type="button"
      className="book-wrap relative mx-auto block h-[168px] w-full max-w-[92px] text-left transition hover:-translate-y-1 focus:outline-none"
      aria-label={`打开 ${book.year} 手账本，共 ${pageCount} 页`}
      onClick={onOpen}
    >
      <div className="absolute -bottom-[8px] left-[8px] h-[12px] w-[80%] rounded-full bg-[#5C3518]/28 blur-[4px]" />
      <div className="absolute bottom-[2px] left-[3px] h-[158px] w-[16px] rounded-l-[5px] bg-[linear-gradient(90deg,rgba(77,46,24,0.22),rgba(255,255,255,0.06),transparent)] shadow-[5px_0_6px_rgba(76,45,21,0.18)]" />
      <div
        className="book-cover absolute inset-x-0 bottom-0 h-[165px] overflow-hidden rounded-r-[8px] rounded-l-[4px] border border-black/5"
        style={
          {
            "--book-cover": palette.cover,
            "--book-spine": palette.spine,
            "--book-edge": palette.edge,
            "--book-shadow": palette.shadow,
            "--book-text": palette.text,
            "--book-ribbon": palette.ribbon,
          } as React.CSSProperties
        }
      >
        <div className="absolute left-0 top-0 h-full w-[18px] bg-[linear-gradient(90deg,rgba(93,55,25,0.18),rgba(255,255,255,0.08)_42%,transparent_78%),linear-gradient(180deg,var(--book-edge),var(--book-spine))] shadow-[inset_-2px_0_4px_rgba(81,47,20,0.16)]" />
        <div className="absolute left-[20px] top-[9px] h-[145px] w-[calc(100%-30px)] rounded-[5px] border border-[#6F4728]/5 shadow-[inset_0_1px_0_rgba(255,255,255,0.07)]" />
        <div className="absolute left-[8px] top-8 h-px w-7 bg-[#6A4322]/18" />
        <div className="absolute left-[8px] top-[39px] h-px w-6 bg-[#6A4322]/16" />
        <div className="absolute left-[8px] bottom-8 h-px w-7 bg-[#6A4322]/16" />
        <div className="relative z-10 grid h-full content-start px-2 pl-[22px] pt-[26px] text-center" style={{ color: palette.text }}>
          <div className="font-song text-[31px] leading-none tracking-[0.02em] drop-shadow-[0_1px_0_rgba(255,255,255,0.25)]">{book.year}</div>
          <PlantMark color={palette.plant} variant={book.plant} />
          <div className="mx-auto mt-[9px] h-px w-9 bg-current opacity-[0.16]" />
          <div className="mt-[8px] text-[12px] leading-none opacity-80">{pageCount} 页</div>
          <div className="mt-[8px] text-[12px] leading-none tracking-[0.08em] opacity-80">{book.title}</div>
        </div>
      </div>
      <div className="absolute bottom-[-28px] left-[20px] z-[18] h-[31px] w-[12px] bg-[linear-gradient(90deg,rgba(90,52,25,0.12),var(--ribbon-color),rgba(255,255,255,0.18))] shadow-[0_3px_4px_rgba(80,49,23,0.16)] [clip-path:polygon(0_0,100%_0,100%_100%,50%_80%,0_100%)]" style={{ "--ribbon-color": palette.ribbon } as React.CSSProperties} />
    </button>
  );
}

function PlantMark({ color, variant }: { color: string; variant: BookYear["plant"] }) {
  const petals = variant === "flower";

  return (
    <div className="relative mx-auto mt-[14px] h-[30px] w-[38px] opacity-[0.72]" style={{ color }}>
      <div className="absolute bottom-0 left-1/2 h-[30px] w-[1.4px] -translate-x-1/2 rotate-[-5deg] rounded-full bg-current" />
      <div className="absolute bottom-[10px] left-[10px] h-[12px] w-[7px] -rotate-45 rounded-[50%] border border-current bg-current/10" />
      <div className="absolute bottom-[14px] right-[10px] h-[12px] w-[7px] rotate-45 rounded-[50%] border border-current bg-current/10" />
      <div className="absolute bottom-[3px] left-[14px] h-[10px] w-[6px] -rotate-45 rounded-[50%] border border-current bg-current/10" />
      <div className="absolute bottom-[5px] right-[13px] h-[10px] w-[6px] rotate-45 rounded-[50%] border border-current bg-current/10" />
      {petals ? (
        <>
          <span className="absolute left-[8px] top-[1px] h-[7px] w-[7px] rounded-full border border-current" />
          <span className="absolute left-[21px] top-[4px] h-[8px] w-[8px] rounded-full border border-current" />
          <span className="absolute left-[15px] top-[-3px] h-[9px] w-[9px] rounded-full border border-current" />
        </>
      ) : null}
      {variant === "sprig" ? (
        <>
          <span className="absolute left-[6px] top-[7px] h-[4px] w-[4px] rounded-full bg-[#F8EAD0]" />
          <span className="absolute right-[8px] top-[2px] h-[4px] w-[4px] rounded-full bg-[#F8EAD0]" />
          <span className="absolute right-[14px] top-[12px] h-[3px] w-[3px] rounded-full bg-[#F8EAD0]" />
        </>
      ) : null}
    </div>
  );
}

function NewBookSlot({ onCreate }: { onCreate: () => void }) {
  return (
    <button className="relative mx-auto h-[168px] w-full max-w-[92px] text-[#6F553C]" onClick={onCreate}>
      <div className="new-book-slot absolute inset-x-0 bottom-0 grid h-[160px] place-items-center rounded-[9px] bg-[#F8EBD6]/25 shadow-[inset_0_0_14px_rgba(255,255,255,0.14),0_8px_14px_rgba(82,51,26,0.10)] backdrop-blur-[1px]">
        <div className="relative z-10 -translate-y-1 text-center">
          <Plus className="mx-auto" size={28} strokeWidth={1.85} />
          <div className="mt-4 text-[12px] leading-5 tracking-[0.02em] text-[#6F553C]">新增一页</div>
        </div>
      </div>
    </button>
  );
}

function DeskDecoration() {
  return (
    <div className="pointer-events-none absolute bottom-[-8px] right-[-58px] z-[14] h-[184px] w-[132px] origin-bottom-right scale-[0.82] opacity-[0.65]">
      <div className="absolute bottom-[26px] right-[65px] h-[89px] w-[47px] rotate-[-10deg] rounded-[3px] border border-[#D8C5AD] bg-[#FBF4E8]/80 shadow-[0_8px_12px_rgba(96,60,31,0.10)]" />
      <div className="absolute bottom-[30px] right-[45px] h-[96px] w-[52px] rotate-[7deg] rounded-[3px] border border-[#D8C5AD] bg-[linear-gradient(180deg,#FFF9EF,#EFE0C9)] opacity-90 shadow-[0_8px_12px_rgba(96,60,31,0.10)]" />
      <div className="absolute bottom-[13px] right-[18px] h-[16px] w-[92px] rounded-[50%] bg-[#F2E3C9]/70 blur-[1px]" />
      <div className="absolute bottom-[14px] right-[28px] h-[67px] w-[45px] rounded-b-[22px] rounded-t-[15px] border border-[#D7BFA0] bg-[radial-gradient(circle_at_35%_25%,rgba(255,255,255,0.72),transparent_20%),radial-gradient(circle_at_60%_70%,rgba(170,119,74,0.10)_0_1px,transparent_2px),linear-gradient(180deg,#FFF3E3,#E6C7A5)] shadow-[0_10px_14px_rgba(82,52,28,0.16)]" />
      <div className="absolute bottom-[78px] right-[42px] h-[23px] w-[19px] rounded-t-full border border-[#D7BFA0] bg-[#F1D8B9]" />
      <DryStem bottom={96} right={51} height={112} rotate="-28deg" />
      <DryStem bottom={95} right={49} height={126} rotate="-7deg" />
      <DryStem bottom={96} right={45} height={118} rotate="18deg" />
      <DryStem bottom={95} right={44} height={102} rotate="37deg" />
      <DryFlower bottom={194} right={86} />
      <DryFlower bottom={205} right={54} />
      <DryFlower bottom={181} right={31} />
      <DryFlower bottom={157} right={77} />
      <DryFlower bottom={172} right={58} />
      <div className="absolute bottom-[25px] right-[12px] h-[25px] w-[94px] rounded-[50%] border-t border-[#F8EEDC]/90 opacity-80" />
    </div>
  );
}

function DryStem({ bottom, right, height, rotate }: { bottom: number; right: number; height: number; rotate: string }) {
  return <div className="absolute w-px origin-bottom bg-[#B8824F]" style={{ bottom, right, height, rotate }} />;
}

function DryFlower({ bottom, right }: { bottom: number; right: number }) {
  return (
    <div className="absolute h-[15px] w-[15px] text-[#F4DEB8]" style={{ bottom, right }}>
      <span className="absolute left-[5px] top-0 h-[6px] w-[5px] rounded-full bg-current" />
      <span className="absolute bottom-0 left-[5px] h-[6px] w-[5px] rounded-full bg-current" />
      <span className="absolute left-0 top-[5px] h-[5px] w-[6px] rounded-full bg-current" />
      <span className="absolute right-0 top-[5px] h-[5px] w-[6px] rounded-full bg-current" />
      <span className="absolute left-[6px] top-[6px] h-[3px] w-[3px] rounded-full bg-[#D3A46B]" />
    </div>
  );
}

function BookPagesPanel({
  book,
  journalId,
  pages,
  loading,
  onClose,
  onCreate,
  onOpenPage,
}: {
  book: BookYear;
  journalId?: string;
  pages: PageBrief[];
  loading: boolean;
  onClose: () => void;
  onCreate: () => void;
  onOpenPage: (page: PageBrief) => void;
}) {
  return (
    <div className="absolute inset-x-3 bottom-3 top-[88px] z-[80] flex flex-col overflow-hidden rounded-[24px] border border-[#eadcc9]/75 bg-[#fffaf4]/97 shadow-[0_24px_60px_rgba(79,49,24,0.28)] backdrop-blur">
      <div className="flex items-center gap-3 border-b border-[#eadcc9]/60 px-4 py-3">
        <div>
          <div className="font-song text-[22px] font-semibold text-[#4f3d2c]">{book.year} 手账本</div>
          <div className="mt-1 text-xs text-[#8a7a68]">{pages.length} 页记录</div>
        </div>
        <div className="flex-1" />
        <button
          type="button"
          className="grid h-9 w-9 place-items-center rounded-full text-[#7d6d5d] hover:bg-[#f4eadc]"
          aria-label="关闭手账本"
          onClick={onClose}
        >
          <X size={18} />
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {loading ? (
          <div className="grid h-full place-items-center text-sm text-[#8a7a68]">正在翻开手账本…</div>
        ) : pages.length > 0 ? (
          <div className="grid gap-3">
            {pages.map((page) => (
              <button
                key={page.id}
                type="button"
                className="flex items-center gap-3 rounded-[18px] border border-[#eadcc9]/58 bg-[#fffdf8] px-4 py-3 text-left shadow-[0_6px_16px_rgba(111,82,51,0.055)] transition hover:-translate-y-0.5 hover:border-[#d8b994]"
                onClick={() => onOpenPage(page)}
              >
                <div className="grid h-11 w-11 shrink-0 place-items-center rounded-[14px] bg-[#f1e3d1] text-xl">
                  {page.mood ? moodIcon(String(page.mood)) : "✦"}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium text-[#4f3d2c]">{page.title || "未命名的一页"}</div>
                  <div className="mt-1 text-xs text-[#8a7a68]">{page.page_date || "未设置日期"}</div>
                </div>
                <ChevronRight size={18} className="shrink-0 text-[#b59b80]" />
              </button>
            ))}
          </div>
        ) : (
          <div className="grid h-full place-items-center text-center">
            <div>
              <div className="font-song text-xl text-[#5f4b38]">这一年还没有记录</div>
              <div className="mt-2 text-sm text-[#8a7a68]">{journalId ? "写下这一年的第一篇吧" : "保存后会自动创建对应年份手账本"}</div>
              <button
                type="button"
                className="mt-5 rounded-full bg-gradient-to-b from-[#c8a37e] to-[#a97852] px-6 py-2.5 text-sm font-medium text-white shadow-[0_8px_18px_rgba(139,93,52,0.16)]"
                onClick={onCreate}
              >
                新增一页
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function LibrarySceneStyle() {
  return (
    <style>{`
      .library-page::before {
        content: "";
        position: absolute;
        inset: 0;
        pointer-events: none;
        opacity: 0.34;
        background-image:
          radial-gradient(rgba(118, 83, 52, 0.14) 0.55px, transparent 0.7px),
          radial-gradient(rgba(255, 255, 255, 0.62) 0.55px, transparent 0.8px);
        background-position: 0 0, 8px 7px;
        background-size: 18px 18px, 22px 22px;
        mix-blend-mode: multiply;
      }

      .paper-rip {
        filter: drop-shadow(0 7px 8px rgba(105, 74, 48, 0.11));
        clip-path: polygon(
          0 0, 100% 0, 100% 64%, 96% 59%, 92% 67%, 88% 61%, 84% 66%, 80% 60%, 76% 65%,
          72% 59%, 68% 66%, 64% 62%, 60% 68%, 56% 61%, 52% 66%, 48% 62%, 44% 69%,
          40% 61%, 36% 67%, 32% 62%, 28% 69%, 24% 62%, 20% 68%, 16% 61%, 12% 66%,
          8% 60%, 4% 66%, 0 61%
        );
      }

      .paper-rip::before {
        content: "";
        position: absolute;
        inset: 0;
        opacity: 0.32;
        background-image: radial-gradient(rgba(120, 88, 61, 0.18) 0.5px, transparent 0.6px);
        background-size: 12px 12px;
      }

      .paper-shadow {
        background: linear-gradient(180deg, rgba(119, 81, 49, 0.12), transparent);
        filter: blur(5px);
      }

      .library-shelf-scroll {
        scrollbar-width: none;
      }

      .library-shelf-scroll::-webkit-scrollbar {
        display: none;
      }

      .library-shelf-scroll::before {
        content: "";
        position: sticky;
        top: 0;
        z-index: 40;
        display: block;
        height: 16px;
        margin: -12px -18px 0;
        pointer-events: none;
        background: linear-gradient(180deg, rgba(109, 68, 32, 0.16), transparent);
      }

      .shelf-board {
        background-image:
          linear-gradient(180deg, rgba(255,255,255,0.56), rgba(255,255,255,0.12) 34%, rgba(129,79,35,0.12)),
          repeating-linear-gradient(96deg, rgba(124,77,34,0.12) 0 1px, transparent 1px 21px),
          linear-gradient(90deg, rgba(144,91,42,0.18), rgba(255,255,255,0.38) 18%, transparent 62%, rgba(124,78,35,0.10));
        box-shadow: 0 -2px 0 rgba(255,255,255,0.48) inset, 0 8px 14px rgba(78,47,22,0.26);
      }

      .book-cover {
        background:
          radial-gradient(circle at 25% 18%, rgba(255,255,255,0.035), transparent 22%),
          radial-gradient(circle at 88% 84%, rgba(71,43,20,0.09), transparent 36%),
          repeating-linear-gradient(4deg, rgba(255,255,255,0.016) 0 1px, transparent 1px 10px),
          repeating-linear-gradient(94deg, rgba(78,50,30,0.045) 0 1px, transparent 1px 12px),
          linear-gradient(100deg, var(--book-spine) 0 18px, var(--book-cover) 19px 100%);
        box-shadow:
          8px 11px 15px rgba(70,40,18,0.30),
          inset 2px 0 0 rgba(255,255,255,0.07),
          inset -6px 0 10px rgba(87,52,25,0.17),
          inset 0 -5px 8px rgba(82,49,22,0.14);
      }

      .book-cover::before {
        content: "";
        position: absolute;
        inset: 0;
        opacity: 0.28;
        background-image:
          radial-gradient(rgba(75, 50, 30, 0.18) 0.34px, transparent 0.54px),
          radial-gradient(rgba(255,255,255,0.10) 0.26px, transparent 0.50px),
          repeating-linear-gradient(84deg, rgba(255,255,255,0.016) 0 1px, transparent 1px 12px);
        background-position: 0 0, 4px 5px, 0 0;
        background-size: 9px 9px, 12px 12px, 100% 100%;
      }

      .book-cover::after {
        content: "";
        position: absolute;
        top: 6px;
        right: 2px;
        width: 4px;
        height: calc(100% - 12px);
        border-radius: 999px;
        background: linear-gradient(90deg, rgba(255,255,255,0.08), rgba(255,255,255,0.02), rgba(92,56,26,0.14));
      }

      .new-book-slot {
        border: 1.35px dashed rgba(255, 255, 255, 0.76);
      }

      .new-book-slot::before {
        content: "";
        position: absolute;
        inset: 1px;
        border-radius: 8px;
        background:
          radial-gradient(circle at 20% 20%, rgba(255,255,255,0.16), transparent 25%),
          repeating-linear-gradient(90deg, rgba(125,80,40,0.05) 0 1px, transparent 1px 24px);
      }
    `}</style>
  );
}

function mergePages(remotePages: PageBrief[], localPages: PageResponse[]): PageBrief[] {
  const merged = new Map<string, PageBrief>();
  [...localPages, ...remotePages].forEach((page) => {
    merged.set(page.id, page);
  });
  return Array.from(merged.values()).sort((a, b) => String(b.created_at ?? b.page_date ?? "").localeCompare(String(a.created_at ?? a.page_date ?? "")));
}

function journalYear(name: string, settings?: Record<string, unknown> | null) {
  const configuredYear = String(settings?.year ?? "").trim();
  if (/^\d{4}$/.test(configuredYear)) return configuredYear;
  return name.match(/(?:19|20)\d{2}/)?.[0];
}

function pageYear(page: Pick<PageResponse, "page_date" | "created_at">) {
  return String(page.page_date ?? page.created_at ?? "").slice(0, 4);
}

function moodIcon(mood: string) {
  return (
    {
      开心: "😊",
      平静: "😌",
      放松: "😮‍💨",
      感动: "🥹",
      兴奋: "🤩",
      甜蜜: "🥰",
      发呆: "🤔",
      困倦: "😴",
      低落: "😔",
      难过: "😢",
      焦虑: "😟",
      愤怒: "😡",
    } as Record<string, string>
  )[mood] ?? "✦";
}

function chunkShelfItems(items: ShelfItem[], size: number): ShelfItem[][] {
  return Array.from({ length: Math.ceil(items.length / size) }, (_, index) => items.slice(index * size, index * size + size));
}
