"use client";

import { useEffect, useRef } from "react";
import {
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";

type Price = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
};

type Band = {
  date: string;
  basis: number;
  upper: number;
  lower: number;
};

type Trigger = {
  date: string;
  trigger_type: "LONG" | "SHORT" | "STOP";
  trigger_price: number;
};

export function PriceChart({
  prices,
  indicators,
  triggers,
}: {
  prices: Price[];
  indicators: Band[];
  triggers: Trigger[];
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || prices.length === 0) return;

    const chart: IChartApi = createChart(ref.current, {
      height: 420,
      layout: {
        background: { type: ColorType.Solid, color: "#ffffff" },
        textColor: "#6b675f",
      },
      grid: {
        vertLines: { color: "#eeeae2" },
        horzLines: { color: "#eeeae2" },
      },
      rightPriceScale: { borderColor: "#ddd8ce" },
      timeScale: { borderColor: "#ddd8ce" },
    });

    const candles = chart.addSeries(CandlestickSeries, {
      upColor: "#1f7a4c",
      downColor: "#b42318",
      borderVisible: false,
      wickUpColor: "#1f7a4c",
      wickDownColor: "#b42318",
    });
    candles.setData(
      prices.map((p) => ({
        time: p.date as Time,
        open: Number(p.open),
        high: Number(p.high),
        low: Number(p.low),
        close: Number(p.close),
      })),
    );

    const upper = chart.addSeries(LineSeries, {
      color: "#2563eb",
      lineWidth: 2,
      title: "Upper",
    });
    const lower = chart.addSeries(LineSeries, {
      color: "#ea580c",
      lineWidth: 2,
      title: "Lower",
    });
    const basis = chart.addSeries(LineSeries, {
      color: "#64748b",
      lineWidth: 2,
      title: "Basis",
    });

    upper.setData(
      indicators.map((i) => ({ time: i.date as Time, value: Number(i.upper) })),
    );
    lower.setData(
      indicators.map((i) => ({ time: i.date as Time, value: Number(i.lower) })),
    );
    basis.setData(
      indicators.map((i) => ({ time: i.date as Time, value: Number(i.basis) })),
    );

    const markers: SeriesMarker<Time>[] = triggers.map((t) => {
      const color =
        t.trigger_type === "LONG"
          ? "#1f7a4c"
          : t.trigger_type === "SHORT"
            ? "#b42318"
            : "#a16207";
      return {
        time: t.date as Time,
        position: t.trigger_type === "SHORT" ? "aboveBar" : "belowBar",
        color,
        shape: t.trigger_type === "STOP" ? "circle" : "arrowUp",
        text: t.trigger_type,
      };
    });
    // Prefer arrowDown for SHORT
    for (const m of markers) {
      const match = triggers.find((t) => t.date === m.time);
      if (match?.trigger_type === "SHORT") {
        m.shape = "arrowDown";
        m.position = "aboveBar";
      }
    }
    createSeriesMarkers(candles as ISeriesApi<"Candlestick">, markers);

    chart.timeScale().fitContent();

    const onResize = () => {
      if (!ref.current) return;
      chart.applyOptions({ width: ref.current.clientWidth });
    };
    onResize();
    window.addEventListener("resize", onResize);

    return () => {
      window.removeEventListener("resize", onResize);
      chart.remove();
    };
  }, [prices, indicators, triggers]);

  return <div ref={ref} className="w-full" />;
}
