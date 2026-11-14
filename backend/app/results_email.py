"""Builds the vote-results report sent to the APC email: percentages for every question,
a simple bar chart (table-based, for broad email-client support) and a link to the live
dashboard."""
from datetime import datetime, timezone
from html import escape

STATUS_TEXT = {"open": "Votare în curs", "closed": "Votare încheiată"}


def _option_color(option: str) -> str:
    normalized = option.strip().lower()
    if normalized.startswith("pentru"):
        return "#2f7d4f"
    if normalized.startswith("împotriv") or normalized.startswith("impotriv"):
        return "#c23b3b"
    return "#2452b5"


def _bar_html(option: dict) -> str:
    percent = max(0.0, min(100.0, float(option.get("percent") or 0)))
    remainder = 100 - percent
    color = _option_color(option.get("option", ""))
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="border-collapse:collapse;margin:0 0 9px;">'
        "<tr>"
        '<td width="130" style="font-size:13px;color:#1f2430;padding:0 8px 0 0;">'
        f"{escape(option.get('option', ''))}</td>"
        '<td style="padding:0;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="border-collapse:collapse;background:#e7ebf2;border-radius:6px;">'
        "<tr>"
        f'<td width="{percent}%" style="background:{color};height:12px;'
        'border-radius:6px;font-size:0;line-height:0;">&nbsp;</td>'
        f'<td width="{remainder}%" style="font-size:0;line-height:0;">&nbsp;</td>'
        "</tr></table></td>"
        '<td width="120" align="right" style="font-size:13px;color:#1f2430;padding:0 0 0 10px;">'
        f"<strong>{percent}%</strong> "
        f'<span style="color:#6b7280;">({option.get("count", 0)})</span></td>'
        "</tr></table>"
    )


def _bar_text(option: dict, width: int = 24) -> str:
    percent = max(0.0, min(100.0, float(option.get("percent") or 0)))
    filled = round(percent / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"{option.get('option', ''):<12} {bar} {percent}% ({option.get('count', 0)})"


def _header(election, results: dict, *, final: bool) -> str:
    status = STATUS_TEXT.get(results.get("status"), results.get("status", ""))
    kind = "Rezultate finale" if final else "Rezultate actualizate"
    generated = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M:%S UTC")
    return kind, status, generated


def build_results_email_text(
    election, results: dict, *, dashboard_url: str = "", final: bool = False, extend_url: str = ""
) -> str:
    kind, status, generated = _header(election, results, final=final)
    lines = [
        f"{kind} – {election.title}",
        f"APC nr. {election.nr_apc or '—'} · {election.str_apc or '—'} · {election.oras or '—'}",
        f"Status: {status} · Raport generat: {generated}",
        "",
        f"Total voturi: {results['total_votes']} din {results['total_tokens']} link-uri "
        f"({results['participation_percent']}% participare)",
        "",
    ]
    if not results.get("questions"):
        lines.append("Nu există întrebări configurate.")
    for question in results.get("questions", []):
        lines.append(f"{question['number']}. {question['text']}")
        for option in question.get("options", []):
            lines.append("  " + _bar_text(option))
        lines.append("")

    if dashboard_url:
        lines += [
            "Rezultatele în timp real (dashboard public):",
            dashboard_url,
            "",
        ]
    if extend_url:
        lines += [
            "Dacă votarea trebuie prelungită, alegeți perioada de prelungire la adresa:",
            extend_url,
            "",
        ]
    lines += [
        "Acest raport este generat automat de sistemul de vot.",
        "Distribuire: APC (rezultate agregate, fără date personale ale votanților).",
    ]
    return "\n".join(lines)


def build_results_email_html(
    election, results: dict, *, dashboard_url: str = "", final: bool = False, extend_url: str = ""
) -> str:
    kind, status, generated = _header(election, results, final=final)

    questions_html = []
    for question in results.get("questions", []):
        bars = "".join(_bar_html(option) for option in question.get("options", []))
        questions_html.append(
            '<div style="margin:0 0 18px;padding:14px 16px;border:1px solid #e2e5ea;'
            'border-radius:10px;background:#fafbfc;">'
            f'<div style="font-weight:600;color:#1f2430;line-height:1.45;margin:0 0 10px;">'
            f"{escape(question['number'])}. {escape(question['text'])}</div>"
            f"{bars}</div>"
        )
    if not questions_html:
        questions_html.append(
            '<p style="margin:0;color:#6b7280;">Nu există întrebări configurate.</p>'
        )

    dashboard_block = ""
    if dashboard_url:
        dashboard_block = (
            '<div style="margin:20px 0 0;padding:14px 16px;border:1px solid #c9d6ef;'
            'border-radius:10px;background:#f2f6fd;">'
            '<div style="font-weight:600;color:#1f2430;margin:0 0 6px;">'
            "Rezultate în timp real</div>"
            '<div style="font-size:13px;color:#4b5b76;line-height:1.5;margin:0 0 8px;">'
            " Dashboardul public se actualizează automat și poate fi partajat membrilor APC:"
            "</div>"
            f'<a href="{escape(dashboard_url)}" style="color:#2452b5;word-break:break-all;">'
            f"{escape(dashboard_url)}</a></div>"
        )

    extend_block = ""
    if extend_url:
        extend_block = (
            '<div style="margin:16px 0 0;padding:14px 16px;border:1px solid #e3d3a8;'
            'border-radius:10px;background:#fdf8ea;">'
            '<div style="font-weight:600;color:#1f2430;margin:0 0 6px;">Prelungirea votării</div>'
            '<div style="font-size:13px;color:#4b5b76;line-height:1.5;margin:0 0 10px;">'
            "Dacă votarea trebuie prelungită, alegeți perioada la adresa de mai jos:</div>"
            f'<a href="{escape(extend_url)}" style="display:inline-block;padding:9px 16px;border-radius:999px;'
            'background:#2452b5;color:#fff;text-decoration:none;font-weight:600;">Prelungește votarea</a></div>'
        )

    status_color = "#2f7d4f" if results.get("status") == "open" else "#6b7280"

    return f"""<!doctype html>
<html lang="ro">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#1f2430;">
  <div style="max-width:720px;margin:0 auto;padding:28px 18px;">
    <div style="background:#ffffff;border:1px solid #e2e5ea;border-radius:12px;padding:28px 30px;">
      <div style="font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#6b7280;margin:0 0 8px;">
        {escape(kind)}
      </div>
      <h2 style="font-size:20px;line-height:1.4;margin:0 0 6px;">{escape(election.title)}</h2>
      <p style="margin:0 0 18px;font-size:13px;color:#6b7280;">
        APC nr. {escape(election.nr_apc or "—")} · {escape(election.str_apc or "—")} ·
        {escape(election.oras or "—")}
      </p>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
             style="border-collapse:collapse;margin:0 0 20px;">
        <tr>
          <td style="padding:12px 14px;border:1px solid #e2e5ea;border-radius:10px 0 0 10px;background:#fafbfc;">
            <div style="font-size:24px;font-weight:700;">{results['total_votes']}</div>
            <div style="font-size:12px;color:#6b7280;">voturi exprimate</div>
          </td>
          <td style="padding:12px 14px;border:1px solid #e2e5ea;border-left:0;background:#fafbfc;">
            <div style="font-size:24px;font-weight:700;">{results['participation_percent']}%</div>
            <div style="font-size:12px;color:#6b7280;">
              participare ({results['total_votes']}/{results['total_tokens']})
            </div>
          </td>
          <td style="padding:12px 14px;border:1px solid #e2e5ea;border-left:0;border-radius:0 10px 10px 0;background:#fafbfc;">
            <div style="font-size:15px;font-weight:600;color:{status_color};">{escape(status)}</div>
            <div style="font-size:12px;color:#6b7280;">{escape(generated)}</div>
          </td>
        </tr>
      </table>
      {''.join(questions_html)}
      {dashboard_block}
      {extend_block}
      <p style="margin:22px 0 0;font-size:12px;color:#9ca3af;line-height:1.5;">
        Raport generat automat de sistemul de vot. Conține rezultate agregate, fără date
        personale ale votanților.
      </p>
    </div>
  </div>
</body>
</html>"""
