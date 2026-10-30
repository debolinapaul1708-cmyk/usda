import hashlib
import json
import os
import re
from datetime import date, datetime

import pandas as pd
import streamlit as st

st.set_page_config(page_title="ProcureIQ Procurement Portal", page_icon="🏛️", layout="wide")

USERS_FILE = "users.json"
UPLOAD_DIR = "uploads"
BIDS_FILE = "data/sample_bids.csv"
os.makedirs(UPLOAD_DIR, exist_ok=True)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.page = "dashboard"


def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def valid_email(email):
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None


def login_signup():
    st.title("🏛️ ProcureIQ Procurement Portal")
    st.caption("A demonstration procurement and bidding portal. Not affiliated with any government platform.")

    tab_login, tab_signup = st.tabs(["Sign in", "Create account"])

    with tab_login:
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", use_container_width=True)

        if submitted:
            users = load_users()
            if email in users and users[email]["password"] == hash_password(password):
                st.session_state.authenticated = True
                st.session_state.user = {"email": email, "name": users[email]["name"]}
                st.session_state.page = "dashboard"
                st.rerun()
            else:
                st.error("Invalid email or password.")

    with tab_signup:
        with st.form("signup_form", clear_on_submit=False):
            name = st.text_input("Full name")
            company = st.text_input("Company / supplier name")
            email = st.text_input("Email")
            password = st.text_input("Create password", type="password")
            confirm = st.text_input("Confirm password", type="password")
            created = st.form_submit_button("Create account", use_container_width=True)

        if created:
            users = load_users()
            if not name or not company or not valid_email(email):
                st.error("Please enter a valid name, company, and email address.")
            elif email in users:
                st.error("An account with this email already exists.")
            elif len(password) < 6:
                st.error("Password must contain at least 6 characters.")
            elif password != confirm:
                st.error("Passwords do not match.")
            else:
                users[email] = {
                    "name": name,
                    "company": company,
                    "password": hash_password(password),
                    "created_at": datetime.now().isoformat(),
                }
                save_users(users)
                st.success("Account created successfully. Please sign in.")


def load_bids():
    return pd.read_csv(BIDS_FILE)


def supplier_profile_form():
    with st.sidebar:
        st.header("Supplier profile")
        profile = st.session_state.get("supplier_profile", {
            "turnover": 12000000,
            "experience": 6,
            "certifications": "ISO 9001, GST",
            "categories": "Medical Equipment, IT Hardware",
        })

        turnover = st.number_input("Annual turnover (₹)", min_value=0, value=int(profile["turnover"]), step=100000)
        experience = st.number_input("Years of experience", min_value=0, value=int(profile["experience"]))
        certifications = st.text_input("Certifications", value=profile["certifications"])
        categories = st.text_input("Preferred categories", value=profile["categories"])

        st.session_state.supplier_profile = {
            "turnover": turnover,
            "experience": experience,
            "certifications": certifications,
            "categories": categories,
        }

        st.divider()
        if st.button("Sign out", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.page = "dashboard"
            st.rerun()

    return st.session_state.supplier_profile


def evaluate_bid(bid, profile):
    required = [x.strip().lower() for x in str(bid["required_certifications"]).split(";") if x.strip()]
    supplier_certs = [x.strip().lower() for x in profile["certifications"].split(",") if x.strip()]
    supplier_cats = [x.strip().lower() for x in profile["categories"].split(",") if x.strip()]

    missing_certs = [c for c in required if c not in supplier_certs]
    turnover_ok = profile["turnover"] >= float(bid["min_turnover"])
    experience_ok = profile["experience"] >= int(bid["min_experience_years"])
    category_ok = str(bid["category"]).strip().lower() in supplier_cats

    checks = [
        {"name": "Minimum turnover", "status": "Met" if turnover_ok else "Unmet",
         "detail": f"Required ₹{float(bid['min_turnover']):,.0f}; entered ₹{profile['turnover']:,.0f}"},
        {"name": "Minimum experience", "status": "Met" if experience_ok else "Unmet",
         "detail": f"Required {bid['min_experience_years']} years; entered {profile['experience']} years"},
        {"name": "Certifications", "status": "Met" if not missing_certs else "Partially met",
         "detail": "All required certifications are available" if not missing_certs else f"Missing: {', '.join(missing_certs)}"},
        {"name": "Category match", "status": "Met" if category_ok else "Review",
         "detail": f"Bid category: {bid['category']}"},
    ]

    weights = {"Met": 1.0, "Partially met": 0.5, "Review": 0.5, "Unmet": 0.0}
    score = round(sum(weights[c["status"]] for c in checks) / len(checks) * 100)

    if score >= 85:
        result, color = "Eligible", "green"
    elif score >= 60:
        result, color = "Conditionally eligible", "amber"
    else:
        result, color = "Not eligible", "red"

    return score, result, color, checks


def trust_badges(bid):
    badges = []
    if "gst" in str(bid["required_certifications"]).lower():
        badges.append("✅ GST required")
    if float(bid["min_turnover"]) >= 10000000:
        badges.append("📦 Delivery history expected")
    if int(bid["min_experience_years"]) >= 5:
        badges.append("⚠️ High-experience tender")
    return badges


def dashboard():
    profile = supplier_profile_form()
    bids = load_bids()

    st.title("📊 Bidder Dashboard")
    st.caption(f"Welcome, {st.session_state.user['name']} — {st.session_state.user['email']}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active bids", len(bids))
    c2.metric("Closing this month", sum(1 for d in bids["closing_date"] if d.startswith("2026-11")))
    c3.metric("Your experience", f"{profile['experience']} years")
    c4.metric("Your turnover", f"₹{profile['turnover']:,.0f}")

    st.divider()
    st.subheader("Available tenders")

    col_search, col_dept, col_cat = st.columns([2, 1, 1])
    search = col_search.text_input("Search bid title, department, or category")
    departments = ["All departments"] + sorted(bids["department"].unique().tolist())
    categories = ["All categories"] + sorted(bids["category"].unique().tolist())
    selected_department = col_dept.selectbox("Department", departments)
    selected_category = col_cat.selectbox("Category", categories)

    filtered = bids.copy()
    if search:
        filtered = filtered[
            filtered["title"].str.contains(search, case=False, na=False)
            | filtered["department"].str.contains(search, case=False, na=False)
            | filtered["category"].str.contains(search, case=False, na=False)
        ]
    if selected_department != "All departments":
        filtered = filtered[filtered["department"] == selected_department]
    if selected_category != "All categories":
        filtered = filtered[filtered["category"] == selected_category]

    st.dataframe(
        filtered[["bid_id", "title", "department", "closing_date", "bid_amount", "category"]],
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    st.subheader("Analyze and submit documents")

    bid_options = filtered["bid_id"] + " — " + filtered["title"]
    selected = st.selectbox("Select a bid", bid_options)
    bid_id = selected.split(" — ")[0]
    bid = bids[bids["bid_id"] == bid_id].iloc[0]

    score, eligibility, color, checks = evaluate_bid(bid, profile)

    with st.container(border=True):
        c1, c2, c3 = st.columns([4, 1.2, 1.2])
        with c1:
            st.markdown(f"### {bid['title']}")
            st.write(f"**Bid ID:** {bid['bid_id']}  |  **Department:** {bid['department']}")
            st.write(f"**Category:** {bid['category']}  |  **Value:** ₹{float(bid['bid_amount']):,.0f}")
            st.write(f"**Closing date:** {bid['closing_date']}")
            st.write(" ".join(trust_badges(bid)))
        with c2:
            st.metric("Trust score", f"{score}/100")
            st.markdown(f"<span style='font-weight:700'>{eligibility}</span>", unsafe_allow_html=True)
        with c3:
            days_left = (datetime.strptime(str(bid["closing_date"]), "%Y-%m-%d").date() - date.today()).days
            st.metric("Days remaining", max(days_left, 0))

        st.markdown("#### Eligibility checks")
        for check in checks:
            icon = {"Met": "✅", "Partially met": "🟡", "Review": "🔍", "Unmet": "❌"}[check["status"]]
            st.markdown(f"- {icon} **{check['name']}** — {check['status']}. {check['detail']}")

    st.markdown("#### Upload bid documents")
    st.caption("Upload PDF, DOCX, JPG, PNG, XLSX, or CSV documents. Files are stored locally in this demonstration app.")

    documents = st.file_uploader(
        "Upload supporting documents",
        type=["pdf", "docx", "jpg", "jpeg", "png", "xlsx", "csv"],
        accept_multiple_files=True,
    )

    required_documents = {
        "Company registration": ["registration", "incorporation", "company"],
        "GST certificate": ["gst"],
        "Turnover certificate": ["turnover", "financial", "balance"],
        "Experience certificate": ["experience", "work", "completion"],
        "Technical specification sheet": ["technical", "specification", "catalog"],
    }

    uploaded_names = [document.name.lower() for document in documents] if documents else []
    document_status = []

    for label, keywords in required_documents.items():
        matched = any(any(keyword in name for keyword in keywords) for name in uploaded_names)
        document_status.append({"Document": label, "Status": "Uploaded" if matched else "Pending"})

    st.dataframe(pd.DataFrame(document_status), use_container_width=True, hide_index=True)

    if documents:
        saved = []
        for document in documents:
            safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", document.name)
            path = os.path.join(UPLOAD_DIR, f"{st.session_state.user['email'].replace('@','_')}__{bid_id}__{safe_name}")
            with open(path, "wb") as f:
                f.write(document.getbuffer())
            saved.append(document.name)

        st.success(f"Uploaded {len(saved)} document(s): {', '.join(saved)}")
    else:
        st.info("Upload the required documents to complete your bid submission.")

    pending = [row["Document"] for row in document_status if row["Status"] == "Pending"]

    if st.button("Submit bid", type="primary", use_container_width=True):
        if pending:
            st.error(f"Cannot submit. Pending documents: {', '.join(pending)}")
        elif eligibility == "Not eligible":
            st.error("Cannot submit. The supplier profile does not meet mandatory eligibility requirements.")
        else:
            st.success("Bid submitted successfully for review.")

    st.divider()
    st.subheader("Payment SLA milestone checklist")
    milestones = [
        ("Delivered", "Completed", "2026-10-12"),
        ("Accepted", "Completed", "2026-10-18"),
        ("Invoice raised", "Completed", "2026-10-20"),
        ("Payment due", "Pending", "2026-11-19"),
    ]
    for stage, status, due in milestones:
        icon = "✅" if status == "Completed" else "⏳"
        st.markdown(f"- {icon} **{stage}** — {status} — due {due}")


if not st.session_state.authenticated:
    login_signup()
else:
    dashboard()
