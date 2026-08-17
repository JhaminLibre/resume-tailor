// Usage: node build_resume.js <spec.json> <output.docx>
//
// spec.json shape:
// {
//   "summary": "...",
//   "skills": "SQL \u2022 dbt \u2022 ...",
//   "roles": [
//     {
//       "title": "Senior Analytics Engineer",
//       "company": "Promise",
//       "location": "Oakland, CA",
//       "dates": "Mar 2026 \u2013 Jul 2026",
//       "subtitle": "Government payments platform ...",   // optional
//       "bullets": ["...", "..."]
//     }
//   ],
//   "education": ["University of Tokyo, Tokyo, JP | Master of Engineering in Material Engineering | 2011", "..."]
// }
//
// Replicates the exact styling of Matthew's real template: Calibri-esque
// default font, name size 34/color 1F1F1F, contact size 18/color 444444,
// section headings bold+caps+bottom border, role line with right-tab-aligned
// dates, italic muted subtitle, filled-circle bullets. Page: US Letter,
// margins top/bottom 500 twips, left/right 850 twips.

const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, AlignmentType, Tab, TabStopType,
  ExternalHyperlink, LevelFormat, BorderStyle
} = require("docx");

const [, , specPath, outPath] = process.argv;
if (!specPath || !outPath) {
  console.error("Usage: node build_resume.js <spec.json> <output.docx>");
  process.exit(1);
}
const spec = JSON.parse(fs.readFileSync(specPath, "utf8"));

const NAME_COLOR = "1F1F1F";
const MUTED_COLOR = "444444";

function nameLine() {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 40 },
    children: [new TextRun({ text: "Matthew Pennisi", bold: true, size: 34, color: NAME_COLOR })],
  });
}

function contactLine() {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 120 },
    children: [
      new ExternalHyperlink({
        link: "mailto:matt.pennisi@gmail.com",
        children: [new TextRun({ text: "matt.pennisi@gmail.com", size: 18, color: MUTED_COLOR, underline: {} })],
      }),
      new TextRun({ text: " | (908) 208-5023 | ", size: 18, color: MUTED_COLOR }),
      new ExternalHyperlink({
        link: "https://www.linkedin.com/in/matthew-pennisi/",
        children: [new TextRun({ text: "LinkedIn", size: 18, color: MUTED_COLOR, underline: {} })],
      }),
    ],
  });
}

function sectionHeading(text) {
  return new Paragraph({
    spacing: { before: 160, after: 60 },
    border: { bottom: { color: MUTED_COLOR, space: 2, style: BorderStyle.SINGLE, size: 6 } },
    children: [new TextRun({ text, bold: true, caps: true, color: NAME_COLOR, size: 22 })],
  });
}

function bodyPara(text) {
  return new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text, size: 20 })] });
}

function role(title, company, location, dates) {
  return new Paragraph({
    tabStops: [{ type: TabStopType.RIGHT, position: 10540 }],
    spacing: { before: 140, after: 10 },
    children: [
      new TextRun({ text: `${title} `, bold: true, size: 21 }),
      new TextRun({ text: `| ${company} | ${location}`, size: 21 }),
      new TextRun({ children: [new Tab(), dates], italics: true, size: 20 }),
    ],
  });
}

function subtitle(text) {
  return new Paragraph({
    spacing: { after: 40 },
    children: [new TextRun({ text, italics: true, size: 19, color: MUTED_COLOR })],
  });
}

function bullet(text) {
  return new Paragraph({
    numbering: { reference: "bullet-list", level: 0 },
    spacing: { after: 40 },
    children: [new TextRun({ text, size: 20 })],
  });
}

const children = [nameLine(), contactLine()];

children.push(sectionHeading("Summary"), bodyPara(spec.summary));
children.push(sectionHeading("Key Skills"), bodyPara(spec.skills));
children.push(sectionHeading("Professional Experience"));

for (const r of spec.roles) {
  children.push(role(r.title, r.company, r.location, r.dates));
  if (r.subtitle) children.push(subtitle(r.subtitle));
  for (const b of r.bullets) children.push(bullet(b));
}

children.push(sectionHeading("Education"));
for (const e of spec.education) children.push(bodyPara(e));

const doc = new Document({
  numbering: {
    config: [
      {
        reference: "bullet-list",
        levels: [
          {
            level: 0,
            format: LevelFormat.BULLET,
            text: "\u25CF",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } },
          },
        ],
      },
    ],
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 500, bottom: 500, left: 850, right: 850 },
        },
      },
      children,
    },
  ],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(outPath, buf);
  console.log(`Wrote ${outPath}`);
});
