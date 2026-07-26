import { useEffect, useMemo, useRef, useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import { localIsoDate } from "../utils";

const MAX_RANGE_DAYS = 30;
const WEEKDAYS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];

interface DateRangePickerProps {
  startDate: string;
  endDate: string;
  onChange: (startDate: string, endDate: string) => void;
}

function parseLocalDate(value: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return null;
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}

function startOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function addDays(date: Date, days: number): Date {
  const result = new Date(date);
  result.setDate(result.getDate() + days);
  return result;
}

function formatBrazilianDate(value: string): string {
  const date = parseLocalDate(value);
  return date ? date.toLocaleDateString("pt-BR") : "";
}

function monthLabel(date: Date): string {
  const label = date.toLocaleDateString("pt-BR", {
    month: "long",
    year: "numeric",
  });
  return label.charAt(0).toUpperCase() + label.slice(1);
}

function buildCalendarDays(month: Date): Array<Date | null> {
  const first = startOfMonth(month);
  const lastDay = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const days: Array<Date | null> = Array.from({ length: first.getDay() }, () => null);
  for (let day = 1; day <= lastDay; day += 1) {
    days.push(new Date(month.getFullYear(), month.getMonth(), day));
  }
  while (days.length % 7) days.push(null);
  return days;
}

export function DateRangePicker({
  startDate,
  endDate,
  onChange,
}: DateRangePickerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const initialMonth = parseLocalDate(startDate) || new Date();
  const [open, setOpen] = useState(false);
  const [choosingEnd, setChoosingEnd] = useState(false);
  const [visibleMonth, setVisibleMonth] = useState(startOfMonth(initialMonth));
  const [hoverDate, setHoverDate] = useState("");

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, []);

  const days = useMemo(() => buildCalendarDays(visibleMonth), [visibleMonth]);
  const maximumEnd = startDate
    ? localIsoDate(addDays(parseLocalDate(startDate) || new Date(), MAX_RANGE_DAYS - 1))
    : "";
  const previewEnd = choosingEnd && hoverDate ? hoverDate : endDate;
  const displayValue = startDate
    ? `${formatBrazilianDate(startDate)} — ${formatBrazilianDate(endDate || startDate)}`
    : "Selecione o período";

  const selectDate = (date: Date) => {
    const value = localIsoDate(date);
    if (!startDate || !choosingEnd) {
      onChange(value, value);
      setChoosingEnd(true);
      setHoverDate("");
      return;
    }

    if (value < startDate || value > maximumEnd) return;
    onChange(startDate, value);
    setChoosingEnd(false);
    setHoverDate("");
    setOpen(false);
  };

  const toggleOpen = () => {
    setOpen((current) => {
      const next = !current;
      if (next) {
        setVisibleMonth(startOfMonth(parseLocalDate(startDate) || new Date()));
        setChoosingEnd(false);
        setHoverDate("");
      }
      return next;
    });
  };

  return (
    <div className="date-range-picker" ref={containerRef}>
      <button
        className="date-range-trigger"
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={toggleOpen}
      >
        <span className={startDate ? "" : "date-placeholder"}>{displayValue}</span>
        <CalendarDays size={18} aria-hidden="true" />
      </button>

      {open && (
        <>
          <button
            className="date-range-backdrop"
            type="button"
            tabIndex={-1}
            aria-label="Fechar calendário"
            onClick={() => setOpen(false)}
          />
          <div className="date-range-popover" role="dialog" aria-label="Selecionar período">
            <div className="calendar-heading">
            <button
              className="calendar-nav-button"
              type="button"
              aria-label="Mês anterior"
              onClick={() =>
                setVisibleMonth(
                  new Date(visibleMonth.getFullYear(), visibleMonth.getMonth() - 1, 1),
                )
              }
            >
              <ChevronLeft size={18} />
            </button>
            <strong>{monthLabel(visibleMonth)}</strong>
            <button
              className="calendar-nav-button"
              type="button"
              aria-label="Próximo mês"
              onClick={() =>
                setVisibleMonth(
                  new Date(visibleMonth.getFullYear(), visibleMonth.getMonth() + 1, 1),
                )
              }
            >
              <ChevronRight size={18} />
            </button>
            </div>

            <div className="calendar-weekdays" aria-hidden="true">
              {WEEKDAYS.map((weekday) => <span key={weekday}>{weekday}</span>)}
            </div>
            <div className="calendar-grid" onMouseLeave={() => setHoverDate("")}>
              {days.map((date, index) => {
                if (!date) return <span className="calendar-empty" key={`empty-${index}`} />;
                const value = localIsoDate(date);
                const disabled = Boolean(
                  choosingEnd && startDate && (value < startDate || value > maximumEnd),
                );
                const inRange = Boolean(
                  startDate && previewEnd && value >= startDate && value <= previewEnd,
                );
                const isBoundary = value === startDate || value === previewEnd;
                return (
                  <button
                    className={[
                      "calendar-day",
                      inRange ? "is-in-range" : "",
                      isBoundary ? "is-boundary" : "",
                    ].filter(Boolean).join(" ")}
                    type="button"
                    disabled={disabled}
                    aria-label={date.toLocaleDateString("pt-BR")}
                    aria-pressed={isBoundary}
                    key={value}
                    onMouseEnter={() => {
                      if (!disabled && choosingEnd) setHoverDate(value);
                    }}
                    onClick={() => selectDate(date)}
                  >
                    {date.getDate()}
                  </button>
                );
              })}
            </div>
            <div className="calendar-instruction">
              {choosingEnd
                ? "Agora selecione a data final."
                : "O primeiro clique define a data inicial."}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
