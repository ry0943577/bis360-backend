import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from google import genai

from rag import StandardsIndex, format_context


# =========================================================
# ENVIRONMENT VARIABLES & KEY
# =========================================================

load_dotenv()

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY",
    "AQ.Ab8RN6ImNiAaCum93hEmdR-UdTXOjgGywEFnuQwP9jfQMxz_Nw"
)


# =========================================================
# GEMINI CLIENT
# =========================================================

ai_client = genai.Client(api_key=GEMINI_API_KEY)


# =========================================================
# FASTAPI APP
# =========================================================

app = FastAPI(title="BIS360 API")


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# BIS STANDARDS INDEX
# =========================================================

index = StandardsIndex()


# =========================================================
# SYSTEM INSTRUCTION
# =========================================================

SYSTEM_INSTRUCTION = """
You are BIS360, an intelligent compliance assistant for Indian Standards (BIS).

Your job is to help manufacturers, importers and businesses understand:

- Applicable Indian Standards (IS numbers)
- BIS certification requirements
- ISI Mark
- CRS
- Hallmarking
- Mandatory requirements
- Basic BIS registration/licensing process
- Compliance steps

IMPORTANT RULES:

1. Answer primarily using the BIS Standards Database context provided below.
2. Do not invent an IS number or BIS requirement.
3. If the provided context does not contain enough information, clearly say so.
4. Do not claim that a product is mandatory unless the provided context says it is mandatory.
5. Explain the answer in a simple and structured way.
6. Mention the relevant IS number whenever available.
7. Mention the certification scheme whenever available.
8. Give practical next steps based on the provided information.
9. For information not present in the database, recommend verification through the official BIS Manakonline portal.
"""


# =========================================================
# REQUEST MODEL
# =========================================================

class ChatRequest(BaseModel):
    message: str


# =========================================================
# HOME
# =========================================================

@app.get("/", response_class=HTMLResponse)
def serve_home():
    html_path = os.path.join(
        os.path.dirname(__file__),
        "frontend_app.html"
    )

    if not os.path.exists(html_path):
        return HTMLResponse(
            content="""
            <h2>BIS360 API is running successfully.</h2>
            <p>Frontend file was not found on the backend.</p>
            """,
            status_code=200
        )

    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "BIS360 Gemini Engine",
        "gemini_configured": bool(GEMINI_API_KEY),
    }


# =========================================================
# CHAT
# =========================================================

@app.post("/chat")
def chat(req: ChatRequest):
    message = req.message.strip()

    if not message:
        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty."
        )

    retrieved = index.retrieve(
        message,
        top_k=3
    )

    if not retrieved:
        return {
            "answer": (
                "Mujhe BIS360 ke current standards database mein "
                "is query se related koi specific Indian Standard nahi mila.\n\n"
                "Kripya product ka exact naam, model/category ya IS number "
                "provide karein. Final compliance requirement ke liye "
                "official BIS Manakonline portal par verification zaroor karein."
            ),
            "retrieved": []
        }

    context = format_context(retrieved)

    prompt = f"""
{SYSTEM_INSTRUCTION}

==============================
BIS STANDARDS DATABASE CONTEXT
==============================

{context}

==============================
USER QUERY
==============================

{message}

==============================
RESPONSE FORMAT
==============================

Provide a concise but useful answer.

Use this structure where applicable:

1. Applicable Standard
2. Certification Scheme
3. Mandatory Requirement
4. What the Standard Covers
5. Basic Compliance Steps
6. Important Note

Only include information supported by the database context.
If something is not available in the context, clearly say that it needs verification.
"""

    try:
        response = ai_client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
        )

        answer = response.text

        if not answer:
            answer = (
                "Gemini ne koi text response return nahi kiya. "
                "Please try again."
            )

        return {
            "answer": answer,
            "retrieved": retrieved
        }

    except Exception as e:
        print("\n" + "=" * 60)
        print("GEMINI API ERROR")
        print("=" * 60)
        print(repr(e))
        print("=" * 60 + "\n")

        return {
            "answer": (
                f"**BIS360 Compliance Details (Local Index):**\n\n{context}"
            ),
            "retrieved": retrieved,
            "ai_error": str(e)
        }