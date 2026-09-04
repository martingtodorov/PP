import { Check } from "lucide-react";

const STEPS = [
  ["placed", "trackStepPlaced"],
  ["paid", "trackStepPaid"],
  ["shipped", "trackStepShipped"],
  ["delivered", "trackStepDelivered"],
];

export const TrackTimeline = ({ steps = {}, t }) => (
  <ol className="mt-8 flex items-start" data-testid="track-timeline">
    {STEPS.map(([key, label], i) => {
      const done = !!steps[key];
      const prevDone = i > 0 && !!steps[STEPS[i - 1][0]];
      return (
        <li key={key} className="flex-1 flex flex-col items-center text-center relative">
          {i > 0 && (
            <span className={`absolute top-4 right-1/2 w-full h-0.5 ${prevDone && done ? "bg-coral-500" : "bg-slate-200"}`} aria-hidden />
          )}
          <span className={`relative z-10 w-8 h-8 rounded-full flex items-center justify-center border-2 transition-colors
            ${done ? "bg-coral-600 border-coral-600 text-white" : "bg-white border-slate-300 text-slate-300"}`}
            data-testid={`track-step-${key}-${done ? "done" : "todo"}`}>
            {done ? <Check className="h-4 w-4" /> : <span className="w-2 h-2 rounded-full bg-slate-300" />}
          </span>
          <span className={`mt-2 text-xs sm:text-sm ${done ? "font-semibold text-slate-900" : "text-slate-400"}`}>
            {t(label)}
          </span>
        </li>
      );
    })}
  </ol>
);

export default TrackTimeline;
