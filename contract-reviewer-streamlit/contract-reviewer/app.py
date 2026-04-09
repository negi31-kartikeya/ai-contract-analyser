import streamlit as st
import json
import anthropic
import pdfplumber
from docx import Document
from io import BytesIO

# ---------- Page config ----------
st.set_page_config(
    page_title="Contract Reviewer",
    page_icon="§",
    layout="centered",
)

# ---------- Constants ----------
CONTRACT_TYPES = [
    "Non-Disclosure Agreement (NDA)",
    "Employment Agreement",
    "Freelancer / Consulting Agreement",
    "SaaS / Service Agreement",
    "Vendor / Supplier Agreement",
    "Lease / Rental Agreement",
    "Partnership Agreement",
    "Investment / Term Sheet",
    "Licensing Agreement",
    "Other",
]

RISK_CONFIG = {
    "high": {"color": "#DC2626", "bg": "#FEE2E2", "icon": "⚠️", "border": "#F87171"},
    "medium": {"color": "#D97706", "bg": "#FEF3C7", "icon": "◆", "border": "#FBBF24"},
    "low": {"color": "#2563EB", "bg": "#DBEAFE", "icon": "●", "border": "#60A5FA"},
    "ok": {"color": "#059669", "bg": "#D1FAE5", "icon": "✅", "border": "#34D399"},
}

SYSTEM_PROMPT = """You are an expert contract analyst with deep knowledge of contract law across jurisdictions. Your job is to analyze contracts clause by clause and produce a structured risk report tailored to the user's specific situation.

## Analysis Framework

You will be given:
- The contract text
- The contract type (e.g., NDA, employment, SaaS agreement)
- The jurisdiction governing the contract
- Which party the user represents (their role/side)
- The user's priority (what matters most to them)

Use all of this context to tailor your analysis. For example:
- If the user is the "Receiving Party" in an NDA, flag clauses that expose THEM to risk.
- If the jurisdiction is California, note that non-competes are generally unenforceable.
- If the user's priority is "easy exit," pay extra attention to termination, auto-renewal, and notice periods.
- If the jurisdiction is India, reference the Indian Contract Act where relevant.

## Risk Scoring Guidelines
- HIGH: Clauses that are unusually one-sided against the user, potentially unenforceable, or expose the user to significant liability.
- MEDIUM: Clauses that are somewhat unfavorable or deviate from standard practice but are not deal-breakers.
- LOW: Minor concerns or clauses that are slightly unusual but not materially harmful.
- OK: Standard, balanced, or favorable clauses.

## Output Format
Return ONLY valid JSON with no markdown fences and no preamble. Follow this exact schema:

{
  "contract_type": "string",
  "overall_risk": "high" | "medium" | "low",
  "overall_score": number (1-100, where 100 = very favorable to the user),
  "executive_summary": "string (2-3 sentences summarizing the contract from the user's perspective)",
  "clauses": [
    {
      "title": "string",
      "original_text": "string (abbreviated, max 80 words)",
      "risk_level": "high" | "medium" | "low" | "ok",
      "plain_summary": "string (1-2 sentences, plain English, explain what this means for the USER specifically)",
      "reasoning": "string (why this risk level, referencing jurisdiction-specific rules where relevant)",
      "suggested_edit": "string or null (proposed alternative language that better protects the user, or null if clause is ok)"
    }
  ],
  "missing_clauses": [
    {
      "title": "string",
      "why_important": "string (why this matters for this contract type and the user's situation)"
    }
  ]
}"""

SAMPLE_CONTRACT = """MUTUAL NON-DISCLOSURE AGREEMENT

This Non-Disclosure Agreement ("Agreement") is entered into as of January 15, 2025, by and between Acme Corp ("Disclosing Party") and Beta LLC ("Receiving Party").

1. DEFINITION OF CONFIDENTIAL INFORMATION
"Confidential Information" means any and all information, whether written, oral, electronic, or visual, disclosed by either party to the other, including but not limited to trade secrets, business plans, financial data, customer lists, technical data, inventions, and product designs.

2. OBLIGATIONS OF RECEIVING PARTY
The Receiving Party agrees to: (a) hold all Confidential Information in strict confidence; (b) not disclose Confidential Information to any third party without prior written consent; (c) use Confidential Information solely for the purpose of evaluating a potential business relationship; (d) protect Confidential Information with the same degree of care used to protect its own confidential information, but no less than reasonable care.

3. TERM AND DURATION
This Agreement shall remain in effect for a period of five (5) years from the date of execution. The obligations of confidentiality shall survive termination and continue indefinitely with respect to all Confidential Information disclosed during the term.

4. NON-SOLICITATION
During the term of this Agreement and for a period of three (3) years thereafter, neither party shall directly or indirectly solicit, recruit, or hire any employee, contractor, or consultant of the other party.

5. INTELLECTUAL PROPERTY ASSIGNMENT
Any ideas, inventions, improvements, or works of authorship conceived or developed by the Receiving Party as a result of access to Confidential Information shall be the sole and exclusive property of the Disclosing Party. The Receiving Party hereby irrevocably assigns all rights, title, and interest in such intellectual property to the Disclosing Party.

6. INDEMNIFICATION
The Receiving Party shall indemnify, defend, and hold harmless the Disclosing Party from and against any and all claims, damages, losses, liabilities, costs, and expenses (including reasonable attorneys' fees) arising out of or related to any breach of this Agreement by the Receiving Party, without any limitation on liability.

7. GOVERNING LAW AND DISPUTE RESOLUTION
This Agreement shall be governed by the laws of the State of Delaware. Any dispute arising under this Agreement shall be resolved exclusively through binding arbitration in Wilmington, Delaware, under the rules of the American Arbitration Association.

8. REMEDIES
In the event of a breach, the Disclosing Party shall be entitled to seek injunctive relief, specific performance, and any other remedies available at law or in equity, without the necessity of proving actual damages or posting any bond.

9. GENERAL PROVISIONS
This Agreement constitutes the entire agreement between the parties. No amendment shall be effective unless in writing and signed by both parties."""


# ---------- Custom CSS ----------
def inject_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap');

        .stApp { font-family: 'DM Sans', sans-serif; }

        /* Header */
        .app-header {
            display: flex; align-items: center; gap: 14px;
            padding: 8px 0 24px; border-bottom: 1px solid rgba(255,255,255,0.06); margin-bottom: 32px;
        }
        .app-logo {
            width: 44px; height: 44px; border-radius: 12px;
            background: linear-gradient(135deg, #3B82F6, #8B5CF6);
            display: flex; align-items: center; justify-content: center;
            font-size: 22px; font-weight: 700; color: white;
        }
        .app-title { font-size: 24px; font-weight: 700; color: #F8FAFC; letter-spacing: -0.02em; margin: 0; }
        .app-subtitle { font-size: 13px; color: #64748B; font-family: 'DM Mono', monospace; margin: 0; }

        /* Score ring */
        .score-ring {
            width: 100px; height: 100px; border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            margin: 0 auto;
        }
        .score-inner {
            width: 76px; height: 76px; border-radius: 50%; background: #0F172A;
            display: flex; flex-direction: column; align-items: center; justify-content: center;
        }
        .score-number { font-size: 26px; font-weight: 700; margin: 0; }
        .score-label { font-size: 10px; color: #64748B; margin: 0; }

        /* Risk badge */
        .risk-badge {
            display: inline-block; padding: 4px 14px; border-radius: 20px;
            font-size: 12px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase;
        }

        /* Context bar */
        .context-bar {
            background: rgba(255,255,255,0.03); border-radius: 12px; padding: 14px 20px;
            border: 1px solid rgba(255,255,255,0.06); margin-bottom: 20px;
            font-size: 13px; color: #94A3B8;
        }
        .context-bar strong { color: #CBD5E1; }

        /* Clause card */
        .clause-header {
            display: flex; align-items: center; gap: 12px; padding: 4px 0;
        }
        .clause-icon {
            width: 28px; height: 28px; border-radius: 8px;
            display: inline-flex; align-items: center; justify-content: center; font-size: 13px; flex-shrink: 0;
        }
        .clause-title { flex: 1; font-size: 14px; font-weight: 600; color: #E2E8F0; }
        .clause-badge {
            padding: 3px 10px; border-radius: 6px; font-size: 11px; font-weight: 700;
            text-transform: uppercase; letter-spacing: 0.04em;
        }

        /* Suggestion box */
        .suggestion-box {
            background: rgba(59,130,246,0.08); border: 1px solid rgba(59,130,246,0.2);
            border-radius: 10px; padding: 14px 16px; margin-top: 12px;
        }
        .suggestion-label { font-size: 11px; font-weight: 700; color: #60A5FA; text-transform: uppercase; letter-spacing: 0.06em; margin: 0 0 6px; }
        .suggestion-text { font-size: 13px; color: #93C5FD; line-height: 1.6; font-family: 'DM Mono', monospace; margin: 0; }

        /* Missing clause */
        .missing-box {
            background: rgba(251,191,36,0.06); border: 1px solid rgba(251,191,36,0.15);
            border-radius: 14px; padding: 20px;
        }
        .missing-title { font-size: 14px; font-weight: 600; color: #FDE68A; margin: 0; }
        .missing-desc { font-size: 13px; color: #A3A3A3; line-height: 1.5; margin: 4px 0 0; }

        /* Section label */
        .section-label { font-size: 11px; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.06em; margin: 0 0 6px; }
        .section-text { font-size: 14px; color: #CBD5E1; line-height: 1.6; margin: 0; }

        /* Disclaimer */
        .disclaimer { text-align: center; font-size: 11px; color: #475569; line-height: 1.6; margin-top: 48px; padding-bottom: 32px; }

        /* Risk distribution */
        .risk-dist { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 16px; }
        .risk-dist-item { display: flex; align-items: center; gap: 6px; font-size: 13px; color: #94A3B8; }

        /* Hide streamlit defaults */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stDeployButton {display: none;}
    </style>
    """, unsafe_allow_html=True)


# ---------- Document parsing ----------
def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF using pdfplumber. Falls back to OCR if needed."""
    text_parts = []
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

    full_text = "\n\n".join(text_parts).strip()

    # If pdfplumber found very little text, try OCR
    if len(full_text) < 50:
        try:
            from pdf2image import convert_from_bytes
            import pytesseract
            images = convert_from_bytes(file_bytes)
            ocr_parts = []
            for img in images:
                ocr_parts.append(pytesseract.image_to_string(img))
            ocr_text = "\n\n".join(ocr_parts).strip()
            if len(ocr_text) > len(full_text):
                return ocr_text
        except Exception:
            pass  # OCR dependencies not available, return whatever we have

    return full_text


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX using python-docx."""
    doc = Document(BytesIO(file_bytes))
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_text(uploaded_file) -> str:
    """Route to the right extractor based on file type."""
    file_bytes = uploaded_file.read()
    name = uploaded_file.name.lower()

    if name.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    elif name.endswith(".docx"):
        return extract_text_from_docx(file_bytes)
    elif name.endswith(".txt"):
        return file_bytes.decode("utf-8", errors="replace")
    else:
        return file_bytes.decode("utf-8", errors="replace")


# ---------- Claude API ----------
def analyze_contract(contract_text: str, contract_type: str, jurisdiction: str, user_role: str, priority: str, api_key: str) -> dict:
    """Send contract to Claude for analysis and return parsed JSON."""
    client = anthropic.Anthropic(api_key=api_key)

    user_message = f"""Analyze this contract with the following context:

- Contract type: {contract_type}
- Jurisdiction: {jurisdiction}
- I am: {user_role}
- My priority: {priority or "General balanced review"}

CONTRACT:
{contract_text[:12000]}"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = "".join(block.text for block in response.content if block.type == "text")
    cleaned = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(cleaned)


# ---------- UI Rendering ----------
def render_header():
    st.markdown("""
    <div class="app-header">
        <div class="app-logo">§</div>
        <div>
            <p class="app-title">Contract Reviewer</p>
            <p class="app-subtitle">AI-powered clause analysis</p>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_score_ring(score: int, color: str, border_color: str):
    st.markdown(f"""
    <div class="score-ring" style="background: conic-gradient({color} {score}%, #1E293B {score}%); box-shadow: 0 0 0 6px #0F172A, 0 0 0 7px {border_color}33;">
        <div class="score-inner">
            <p class="score-number" style="color: {color};">{score}</p>
            <p class="score-label">/ 100</p>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_results(analysis: dict, jurisdiction: str, user_role: str, priority: str):
    risk = analysis["overall_risk"]
    rc = RISK_CONFIG[risk]

    # Summary card
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f'<span class="risk-badge" style="background: {rc["bg"]}; color: {rc["color"]};">{risk} risk</span>', unsafe_allow_html=True)
        st.caption(f"📍 {jurisdiction}  ·  👤 {user_role}" + (f"  ·  🎯 {priority}" if priority else ""))
        st.markdown(f"<p style='font-size:14px; color:#CBD5E1; line-height:1.7;'>{analysis['executive_summary']}</p>", unsafe_allow_html=True)
    with col2:
        render_score_ring(analysis["overall_score"], rc["color"], rc["border"])

    # Risk distribution
    counts = {level: 0 for level in RISK_CONFIG}
    for c in analysis["clauses"]:
        counts[c["risk_level"]] = counts.get(c["risk_level"], 0) + 1
    dist_html = "".join(
        f'<span class="risk-dist-item"><span style="color:{RISK_CONFIG[level]["color"]}">{RISK_CONFIG[level]["icon"]}</span> {count} {level}</span>'
        for level, count in counts.items() if count > 0
    )
    st.markdown(f'<div class="risk-dist">{dist_html}</div>', unsafe_allow_html=True)

    st.markdown("---")

    # Clause analysis
    st.subheader("Clause Analysis")
    for i, clause in enumerate(analysis["clauses"]):
        rc_clause = RISK_CONFIG[clause["risk_level"]]
        with st.expander(f'{rc_clause["icon"]}  {clause["title"]}  —  {clause["risk_level"].upper()}'):
            st.markdown(f'<p class="section-label">Plain English</p><p class="section-text">{clause["plain_summary"]}</p>', unsafe_allow_html=True)
            st.markdown(f'<p class="section-label" style="margin-top:14px;">Why this rating</p><p class="section-text">{clause["reasoning"]}</p>', unsafe_allow_html=True)
            if clause.get("suggested_edit"):
                st.markdown(f"""
                <div class="suggestion-box">
                    <p class="suggestion-label">💡 Suggested Edit</p>
                    <p class="suggestion-text">{clause["suggested_edit"]}</p>
                </div>
                """, unsafe_allow_html=True)

    # Missing clauses
    if analysis.get("missing_clauses"):
        st.markdown("---")
        st.subheader("Missing Clauses")
        st.markdown('<div class="missing-box">', unsafe_allow_html=True)
        for m in analysis["missing_clauses"]:
            st.markdown(f"""
            <div style="margin-bottom: 14px; display: flex; gap: 10px;">
                <span style="color: #FBBF24; font-size: 14px; margin-top: 2px;">◇</span>
                <div>
                    <p class="missing-title">{m["title"]}</p>
                    <p class="missing-desc">{m["why_important"]}</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)


# ---------- Session state init ----------
if "step" not in st.session_state:
    st.session_state.step = "intake"
if "analysis" not in st.session_state:
    st.session_state.analysis = None
if "contract_text" not in st.session_state:
    st.session_state.contract_text = ""


def get_api_key() -> str | None:
    """Get API key from sidebar input. User must provide their own key."""
    key = st.session_state.get("user_api_key", "").strip()
    return key if key else None


# ---------- Main app ----------
def main():
    inject_css()

    # Sidebar — API key
    with st.sidebar:
        st.markdown("### 🔑 API Key")
        st.text_input(
            "Anthropic API Key",
            type="password",
            placeholder="sk-ant-...",
            key="user_api_key",
            help="Your key is stored in memory only for this session. It is never saved or logged.",
        )
        api_key = get_api_key()
        if api_key:
            st.success("API key set", icon="✅")
        else:
            st.warning("Enter your Anthropic API key to start.", icon="⚠️")
        st.caption("Get a key at [console.anthropic.com](https://console.anthropic.com/)")
        st.markdown("---")
        st.markdown(
            "<p style='font-size:11px; color:#64748B; line-height:1.5;'>"
            "Your API key stays in your browser session. It is never stored on disk or sent anywhere except directly to the Anthropic API."
            "</p>",
            unsafe_allow_html=True,
        )

    render_header()

    # ===== STEP 1: INTAKE =====
    if st.session_state.step == "intake":
        st.markdown("### Tell us about your contract")
        st.caption("This helps us tailor the analysis to your specific situation.")

        contract_type = st.selectbox("Contract Type *", [""] + CONTRACT_TYPES, index=0)
        jurisdiction = st.text_input("Jurisdiction *", placeholder="e.g., India, California USA, United Kingdom, EU")
        user_role = st.text_input("Which side are you on? *", placeholder="e.g., The service provider, the employee, the receiving party")
        st.caption("This is critical — risk is always relative to which party you are.")
        priority = st.text_input("What's your priority? (optional)", placeholder="e.g., Limiting liability, protecting IP, easy exit, balanced deal")

        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("Continue →", type="primary", disabled=not (contract_type and jurisdiction.strip() and user_role.strip())):
                st.session_state.contract_type = contract_type
                st.session_state.jurisdiction = jurisdiction
                st.session_state.user_role = user_role
                st.session_state.priority = priority
                st.session_state.step = "upload"
                st.rerun()
        with col2:
            if st.button("Try sample NDA"):
                st.session_state.contract_type = "Non-Disclosure Agreement (NDA)"
                st.session_state.jurisdiction = "Delaware, USA"
                st.session_state.user_role = "Receiving Party (Beta LLC)"
                st.session_state.priority = "Balanced deal with reasonable IP and liability protections"
                st.session_state.contract_text = SAMPLE_CONTRACT
                st.session_state.step = "upload"
                st.rerun()

    # ===== STEP 2: UPLOAD =====
    elif st.session_state.step == "upload":
        # Context bar
        st.markdown(f"""
        <div class="context-bar">
            <strong>Type:</strong> {st.session_state.contract_type} &nbsp;·&nbsp;
            <strong>Jurisdiction:</strong> {st.session_state.jurisdiction} &nbsp;·&nbsp;
            <strong>You are:</strong> {st.session_state.user_role}
        </div>
        """, unsafe_allow_html=True)

        if st.button("← Edit details", type="secondary"):
            st.session_state.step = "intake"
            st.rerun()

        # Input method
        input_method = st.radio("How would you like to provide the contract?", ["Upload File", "Paste Text"], horizontal=True)

        contract_text = st.session_state.contract_text

        if input_method == "Upload File":
            uploaded_file = st.file_uploader(
                "Upload your contract",
                type=["pdf", "docx", "txt"],
                help="Supports PDF (including scanned), DOCX, and TXT files up to 20MB.",
            )
            if uploaded_file:
                with st.spinner("Extracting text from document..."):
                    contract_text = extract_text(uploaded_file)
                if contract_text.strip():
                    st.success(f"Extracted {len(contract_text.split())} words from {uploaded_file.name}")
                    with st.expander("Preview extracted text"):
                        st.text(contract_text[:3000] + ("..." if len(contract_text) > 3000 else ""))
                else:
                    st.error("Could not extract text from this file. Please try pasting the text directly.")
        else:
            contract_text = st.text_area(
                "Paste your contract text",
                value=contract_text,
                height=300,
                placeholder="Paste the full contract text here...",
            )

        can_analyze = bool(contract_text.strip()) and bool(api_key)
        if not api_key and contract_text.strip():
            st.info("Enter your Anthropic API key in the sidebar to analyze.")
        if st.button("Analyze Contract", type="primary", disabled=not can_analyze):
            st.session_state.contract_text = contract_text
            st.session_state.step = "analyzing"
            st.rerun()

    # ===== STEP 3: ANALYZING =====
    elif st.session_state.step == "analyzing":
        st.markdown(f"""
        <div style="text-align: center; padding: 60px 20px;">
            <div style="width: 56px; height: 56px; margin: 0 auto 24px; border-radius: 14px;
                background: linear-gradient(135deg, #3B82F6, #8B5CF6);
                display: flex; align-items: center; justify-content: center; font-size: 28px; color: white;">§</div>
            <p style="color: #94A3B8; font-size: 15px; font-weight: 500;">Analyzing your {st.session_state.contract_type.lower()}...</p>
            <p style="color: #475569; font-size: 13px;">Reviewing clauses against {st.session_state.jurisdiction} standards from your perspective as {st.session_state.user_role}</p>
        </div>
        """, unsafe_allow_html=True)

        try:
            with st.spinner(""):
                analysis = analyze_contract(
                    st.session_state.contract_text,
                    st.session_state.contract_type,
                    st.session_state.jurisdiction,
                    st.session_state.user_role,
                    st.session_state.priority,
                    api_key,
                )
            st.session_state.analysis = analysis
            st.session_state.step = "results"
            st.rerun()
        except Exception as e:
            st.error(f"Analysis failed: {str(e)}")
            if st.button("← Back to upload"):
                st.session_state.step = "upload"
                st.rerun()

    # ===== STEP 4: RESULTS =====
    elif st.session_state.step == "results" and st.session_state.analysis:
        render_results(
            st.session_state.analysis,
            st.session_state.jurisdiction,
            st.session_state.user_role,
            st.session_state.priority,
        )

        st.markdown("---")
        if st.button("← Analyze another contract"):
            for key in ["step", "analysis", "contract_text", "contract_type", "jurisdiction", "user_role", "priority"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state.step = "intake"
            st.rerun()

    # Disclaimer
    st.markdown('<p class="disclaimer">This tool provides informational analysis only and does not constitute legal advice. Consult a qualified attorney for legal decisions.</p>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
