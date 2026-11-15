/**
 * AGNI impact slides — 2-slide pitch deck
 * Numbers are from published sources (Cal OES, LA Times, Camp Fire research, ULRI).
 */
const PptxGenJS = require("pptxgenjs");
const path = require("path");
const { applyTheme } = require(
  "/Users/bijinjiby/.claude/skills/synced/09e3118a-7bfe-444f-b372-4c4a6d755a87_a7a4a1ee-5a18-4362-8d7a-4c27329c83a2/pptx/scripts/apply_theme.js"
);

const ASSETS = path.join(__dirname, "assets");
const OUT = path.join(__dirname, "AGNI_Impact_Slides.pptx");

const THEME = {
  name: "AGNI Ember",
  headFontFace: "Arial",
  bodyFontFace: "Arial",
  colors: {
    dk1: "0A0C10",
    lt1: "F5F1EB",
    dk2: "1A222D",
    lt2: "9AA4B2",
    accent1: "FF6B35",
    accent2: "E85D04",
    accent3: "F4A261",
    accent4: "2A9D8F",
    accent5: "E9C46A",
    accent6: "E76F51",
    hlink: "F4A261",
    folHlink: "FF6B35",
  },
};

async function main() {
  const pres = new PptxGenJS();
  pres.defineLayout({ name: "AGNI_WIDE", width: 13.333, height: 7.5 });
  pres.layout = "AGNI_WIDE";
  pres.author = "AGNI";
  pres.title = "AGNI Impact";
  pres.subject = "California 911 surge impact + sponsor stack";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };

  const C = {
    ink: "F5F1EB",
    mute: "9AA4B2",
    ember: "FF6B35",
    gold: "E9C46A",
    teal: "2A9D8F",
    card: "161B22",
    soft: "D0D5DD",
  };

  // ─── SLIDE 1: AGNI fills the slide + impact numbers ───
  const s1 = pres.addSlide();
  s1.addImage({ path: path.join(ASSETS, "bg1.png"), x: 0, y: 0, w: 13.333, h: 7.5 });

  // Giant AGNI watermark — brand returns across the entire slide
  s1.addText("AGNI", {
    x: -0.4,
    y: 1.35,
    w: 14.2,
    h: 4.6,
    fontSize: 280,
    fontFace: "Arial Black",
    color: "FF6B35",
    bold: true,
    align: "center",
    valign: "middle",
    margin: 0,
    isTextBox: true,
    transparency: 82,
  });

  // Top label
  s1.addText("WHEN SURGE HITS CALIFORNIA", {
    x: 0.7,
    y: 0.35,
    w: 12,
    h: 0.35,
    fontSize: 13,
    fontFace: "Arial",
    color: C.ember,
    bold: true,
    charSpacing: 4,
    margin: 0,
    isTextBox: true,
  });

  s1.addText("The return of every unanswered call", {
    x: 0.7,
    y: 0.7,
    w: 12,
    h: 0.55,
    fontSize: 28,
    fontFace: "Arial",
    color: C.ink,
    bold: true,
    margin: 0,
    isTextBox: true,
  });

  // Four impact cards
  const stats = [
    {
      x: 0.55,
      num: "~25M",
      label: "911 calls / year",
      sub: "California statewide volume",
      source: "Cal OES 2025",
    },
    {
      x: 3.75,
      num: "10×",
      label: "surge multiplier",
      sub: "Catastrophic wildfire vs normal",
      source: "Camp Fire research",
    },
    {
      x: 6.95,
      num: "≤10s",
      label: "calm wait target",
      sub: "Answer standard in busy hour",
      source: "CA 9-1-1 Ops Manual",
    },
    {
      x: 10.15,
      num: "BUSY",
      label: "surge wait reality",
      sub: "Lines saturate · holds · drops",
      source: "Eaton · Camp Fire",
    },
  ];

  for (const st of stats) {
    s1.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: st.x,
      y: 1.55,
      w: 2.95,
      h: 3.35,
      fill: { color: "0F1319", transparency: 25 },
      rectRadius: 0.14,
      shadow: { type: "outer", color: "000000", blur: 18, offset: 4, opacity: 0.35 },
    });
    s1.addText(st.num, {
      x: st.x + 0.15,
      y: 1.85,
      w: 2.65,
      h: 1.05,
      fontSize: 48,
      fontFace: "Arial Black",
      color: C.ember,
      bold: true,
      align: "center",
      margin: 0,
      isTextBox: true,
    });
    s1.addText(st.label.toUpperCase(), {
      x: st.x + 0.15,
      y: 2.95,
      w: 2.65,
      h: 0.4,
      fontSize: 13,
      fontFace: "Arial",
      color: C.ink,
      bold: true,
      align: "center",
      charSpacing: 1.2,
      margin: 0,
      isTextBox: true,
    });
    s1.addText(st.sub, {
      x: st.x + 0.2,
      y: 3.4,
      w: 2.55,
      h: 0.7,
      fontSize: 13,
      fontFace: "Arial",
      color: C.soft,
      align: "center",
      margin: 0,
      isTextBox: true,
    });
    s1.addText(st.source, {
      x: st.x + 0.15,
      y: 4.35,
      w: 2.65,
      h: 0.3,
      fontSize: 10,
      fontFace: "Arial",
      color: C.mute,
      align: "center",
      italic: true,
      margin: 0,
      isTextBox: true,
    });
  }

  // Bottom proof strip
  s1.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 0.55,
    y: 5.2,
    w: 12.25,
    h: 1.85,
    fill: { color: "0F1319", transparency: 20 },
    rectRadius: 0.12,
  });

  const proofs = [
    { n: "1,400+", t: "fire-related calls in Pasadena\non Eaton Fire night one" },
    { n: "2,800", t: "calls logged by midnight\nCamp Fire · Butte County" },
    { n: "14 → 8 hrs", t: "west Altadena fire reports\nbefore first evacuation order" },
    { n: "AGNI", t: "catches the overflow\n911 never reaches" },
  ];

  proofs.forEach((p, i) => {
    const x = 0.8 + i * 3.05;
    s1.addText(p.n, {
      x,
      y: 5.4,
      w: 2.8,
      h: 0.45,
      fontSize: 22,
      fontFace: "Arial",
      color: i === 3 ? C.gold : C.ink,
      bold: true,
      margin: 0,
      isTextBox: true,
    });
    s1.addText(p.t, {
      x,
      y: 5.9,
      w: 2.8,
      h: 0.85,
      fontSize: 12,
      fontFace: "Arial",
      color: C.mute,
      margin: 0,
      isTextBox: true,
    });
  });

  s1.addNotes(
    "Sources: Cal OES 9-1-1 Advisory Board (2025 call volume ~24.7M); Camp Fire research (10× surge, 2,800 Butte calls); CA 9-1-1 Ops Manual (10s busy-hour target); LA Times / Pasadena Eaton (1,400+ fire calls; 14 reports before west Altadena order at 3:25am; 8hr lag); ULRI on Eaton: calls faster than dispatch could manage. AGNI does not invent wait-time averages — surge reality is busy/hold/drop."
  );

  // ─── SLIDE 2: Sponsors + how it's used ───
  const s2 = pres.addSlide();
  s2.addImage({ path: path.join(ASSETS, "bg2.png"), x: 0, y: 0, w: 13.333, h: 7.5 });

  s2.addText("BUILT WITH", {
    x: 0.6,
    y: 0.28,
    w: 5,
    h: 0.3,
    fontSize: 12,
    fontFace: "Arial",
    color: C.ember,
    bold: true,
    charSpacing: 3.5,
    margin: 0,
    isTextBox: true,
  });
  s2.addText("Sponsors powering AGNI", {
    x: 0.6,
    y: 0.55,
    w: 6,
    h: 0.45,
    fontSize: 26,
    fontFace: "Arial",
    color: C.ink,
    bold: true,
    margin: 0,
    isTextBox: true,
  });

  const logos = [
    ["logo-elevenlabs.png", "Voice intake"],
    ["logo-gemini.png", "Landmarks · triage"],
    ["logo-bright-data.png", "Signals · closures"],
    ["logo-neon.png", "Incident store"],
    ["logo-twilio.png", "Phone number"],
    ["logo-nasa-firms.png", "Satellite heat"],
    ["logo-openrouteservice.png", "Safe routing"],
  ];

  // Top row of 4, bottom row of 3 centered-ish
  logos.forEach((pair, i) => {
    const [file, role] = pair;
    const row = i < 4 ? 0 : 1;
    const col = i < 4 ? i : i - 4;
    const count = row === 0 ? 4 : 3;
    const startX = row === 0 ? 0.55 : 1.9;
    const gap = 3.1;
    const x = startX + col * gap;
    const y = 1.15 + row * 1.35;
    s2.addImage({
      path: path.join(ASSETS, file),
      x,
      y,
      w: 2.85,
      h: 0.95,
    });
    s2.addText(role, {
      x,
      y: y + 0.95,
      w: 2.85,
      h: 0.28,
      fontSize: 11,
      fontFace: "Arial",
      color: C.mute,
      align: "center",
      margin: 0,
      isTextBox: true,
    });
  });

  // How-used visual
  s2.addImage({
    path: path.join(ASSETS, "how-used.png"),
    x: 0.55,
    y: 3.85,
    w: 12.25,
    h: 3.3,
  });

  s2.addNotes(
    "Sponsors: ElevenLabs (voice), Gemini (landmarks/triage/classifier), Bright Data (SERP/posts/closures), Neon (store/branches), Twilio (number), NASA FIRMS (heat), OpenRouteService (routing). Flow: 911 busy → AGNI overflow → find fire → human decides → warn path. Human confirms every fire, dispatch, and warning."
  );

  await pres.writeFile({ fileName: OUT });
  try {
    await applyTheme(OUT, THEME);
  } catch (err) {
    console.warn("Theme apply skipped:", err.message.split("\n")[0]);
  }
  console.log("Wrote", OUT);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
