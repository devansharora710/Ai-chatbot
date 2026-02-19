# mom_pdf_template.py
import html as html_lib
from datetime import datetime

import markdown


MOM_CSS = """
body {
  font-family: 'Segoe UI', Arial, sans-serif;
  line-height: 1.6;
  color: #333;
  max-width: 800px;
  margin: 40px auto;
  padding: 20px;
}
.header-info {
  background-color: #f8f9fa;
  border-left: 4px solid #3498db;
  padding: 15px;
  margin-bottom: 30px;
  border-radius: 4px;
}
.header-info p {
  margin: 5px 0;
  font-size: 14px;
  color: #555;
}
.header-info strong {
  color: #2c3e50;
  font-weight: 600;
}
h1 {
  color: #2c3e50;
  border-bottom: 3px solid #3498db;
  padding-bottom: 10px;
  margin-top: 0;
}
h2 {
  color: #34495e;
  margin-top: 30px;
  border-bottom: 1px solid #bdc3c7;
  padding-bottom: 5px;
}
ul { line-height: 1.8; }
li { margin-bottom: 8px; }
strong { color: #2980b9; }
code {
  background-color: #ecf0f1;
  padding: 2px 6px;
  border-radius: 3px;
}
table {
  border-collapse: collapse;
  width: 100%;
  margin: 20px 0;
}
th, td {
  border: 1px solid #ddd;
  padding: 12px;
  text-align: left;
}
th {
  background-color: #3498db;
  color: white;
}
.footer {
  margin-top: 40px;
  padding-top: 20px;
  border-top: 1px solid #bdc3c7;
  text-align: center;
  color: #7f8c8d;
  font-size: 12px;
}
"""


def render_mom_html(mom_markdown: str, caller_id: str | None = None) -> str:
    html_content = markdown.markdown(
        mom_markdown,
        extensions=["tables", "fenced_code", "nl2br"],
    )

    current_date = datetime.now().strftime("%B %d, %Y at %I:%M %p IST")
    safe_caller = html_lib.escape(caller_id or "Unknown")
    doc_id = html_lib.escape(datetime.now().strftime("%d%m"))

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
{MOM_CSS}
  </style>
</head>
<body>
  <div class="header-info">
    <p><strong>Caller ID:</strong> {safe_caller}</p>
    <p><strong>Date & Time:</strong> {current_date}</p>
    <p><strong>Agent:</strong> Sarah (Barbie Builders)</p>
  </div>

  {html_content}

  <div class="footer">
    <p>Generated automatically by Barbie Builders AI Sales Assistant</p>
    <p>Document ID: MoM-{safe_caller}-{doc_id}</p>
  </div>
</body>
</html>
"""
