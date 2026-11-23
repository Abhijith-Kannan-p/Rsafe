import { Languages } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, type Lang, type RuleText, type Translations } from "./api";
import { useSession } from "./session";

/**
 * Plain-language rule reasons in English, Hindi or Malayalam. Only the rule texts (title,
 * reason, fix) are translated; record-specific details and the rest of the UI stay in English.
 * Hindi and Malayalam are machine translations and are always labelled as needing review.
 */
type Ctx = {
  lang: Lang;
  setLang: (l: Lang) => void;
  data: Translations | null;
  rule: (ruleId: string, fallback: RuleText) => RuleText & { machine: boolean; lang: Lang };
};

const LangContext = createContext<Ctx | null>(null);
const KEY = "rsafe.lang";
const LANGS: Lang[] = ["en", "hi", "ml"];

function stored(): Lang {
  try {
    const v = localStorage.getItem(KEY);
    return LANGS.includes(v as Lang) ? (v as Lang) : "en";
  } catch {
    return "en";
  }
}

export function LangProvider({ children }: { children: ReactNode }) {
  const { identity } = useSession();
  const [lang, setLangState] = useState<Lang>(stored);
  const [data, setData] = useState<Translations | null>(null);

  useEffect(() => {
    if (!identity || data) return;
    api<Translations>("/rules/i18n").then(setData).catch(() => undefined);
  }, [identity, data]);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem(KEY, l);
    } catch {
      /* private mode: keep it for this visit only */
    }
  }, []);

  const rule = useCallback(
    (ruleId: string, fallback: RuleText) => {
      const t = lang !== "en" ? data?.rules[ruleId]?.[lang] : undefined;
      return t ? { ...t, machine: true, lang } : { ...fallback, machine: false, lang: "en" as Lang };
    },
    [lang, data],
  );

  const value = useMemo(() => ({ lang, setLang, data, rule }), [lang, setLang, data, rule]);
  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

export function useLang() {
  const ctx = useContext(LangContext);
  if (!ctx) throw new Error("useLang must be used inside <LangProvider>");
  return ctx;
}

const HTML_LANG: Record<Lang, string> = { en: "en", hi: "hi", ml: "ml" };
export const htmlLang = (l: Lang) => HTML_LANG[l];

/** "Machine translation · needs review" label, shown wherever translated text appears. */
export function MachineNote({ className = "" }: { className?: string }) {
  const { lang, data } = useLang();
  if (lang === "en") return null;
  return (
    <p className={`flex items-center gap-1.5 text-xs text-violet ${className}`}>
      <Languages className="h-3.5 w-3.5" aria-hidden />
      {data?.languages[lang]?.note ?? "Machine translation. Needs review."}
    </p>
  );
}

export function LanguageSelect() {
  const { lang, setLang } = useLang();
  return (
    <label className="flex items-center gap-1.5 text-xs text-mist">
      <Languages className="h-4 w-4" aria-hidden />
      <span className="sr-only">Language for rule reasons</span>
      <select
        value={lang}
        onChange={(e) => setLang(e.target.value as Lang)}
        className="h-9 rounded-full border border-white/15 bg-bg-mid/70 pl-3 pr-8 text-sm text-cream focus-visible:outline-2 focus-visible:outline-saffron"
      >
        <option value="en">English</option>
        <option value="hi" lang="hi">हिन्दी</option>
        <option value="ml" lang="ml">മലയാളം</option>
      </select>
    </label>
  );
}
