import json
import os
import re


class StandardsIndex:

    def __init__(self, data_path=None):

        # Find standards.json
        if not data_path:
            base_dir = os.path.dirname(__file__)

            possible_paths = [
                os.path.join(base_dir, "data", "standards.json"),
                os.path.join(os.path.dirname(base_dir), "data", "standards.json"),
                os.path.join(os.path.dirname(base_dir), "standards.json"),
            ]

            data_path = None

            for path in possible_paths:
                if os.path.exists(path):
                    data_path = path
                    break

        self.standards = []

        if data_path and os.path.exists(data_path):

            try:
                with open(data_path, "r", encoding="utf-8") as f:
                    self.standards = json.load(f)

                print(
                    f"BIS360: Loaded {len(self.standards)} standards "
                    f"from {data_path}"
                )

            except Exception as e:
                print("BIS360: Error loading standards.json:", repr(e))
                self.standards = []

        else:
            print("BIS360: standards.json not found.")


    # =====================================================
    # NORMALIZE TEXT
    # =====================================================

    def normalize(self, text):

        if text is None:
            return ""

        text = str(text).lower()

        # Replace punctuation with spaces
        text = re.sub(r"[^a-z0-9]+", " ", text)

        # Remove extra spaces
        text = re.sub(r"\s+", " ", text).strip()

        return text


    # =====================================================
    # GET SEARCHABLE TEXT FROM STANDARD
    # =====================================================

    def standard_text(self, item):

        # Supports both your current dataset format
        # and the older field names.

        fields = [
            item.get("is_number", ""),
            item.get("standard_number", ""),

            item.get("product", ""),
            item.get("title", ""),

            item.get("category", ""),
            item.get("product_category", ""),

            item.get("scheme", ""),

            item.get("scope", ""),
            item.get("description", ""),

            item.get("mandatory", ""),
            item.get("is_mandatory", ""),
        ]

        return self.normalize(" ".join(map(str, fields)))


    # =====================================================
    # RETRIEVE RELEVANT STANDARDS
    # =====================================================

    def retrieve(self, query: str, top_k: int = 3):

        if not self.standards:
            return []

        query_normalized = self.normalize(query)

        if not query_normalized:
            return []

        query_tokens = set(query_normalized.split())

        scored_items = []

        for item in self.standards:

            text = self.standard_text(item)

            if not text:
                continue

            item_tokens = set(text.split())

            # ---------------------------------------------
            # Token overlap
            # ---------------------------------------------

            common_tokens = query_tokens.intersection(item_tokens)

            score = len(common_tokens)


            # ---------------------------------------------
            # Exact phrase match
            # ---------------------------------------------

            if query_normalized in text:
                score += 10


            # ---------------------------------------------
            # Important product/IS fields get extra weight
            # ---------------------------------------------

            product_text = self.normalize(
                " ".join([
                    str(item.get("product", "")),
                    str(item.get("title", "")),
                    str(item.get("description", "")),
                ])
            )

            product_tokens = set(product_text.split())

            product_matches = query_tokens.intersection(product_tokens)

            score += len(product_matches) * 2


            # ---------------------------------------------
            # IS number direct match
            # ---------------------------------------------

            is_number = self.normalize(
                item.get(
                    "is_number",
                    item.get("standard_number", "")
                )
            )

            if is_number and is_number in query_normalized:
                score += 20


            # ---------------------------------------------
            # Store matching result
            # ---------------------------------------------

            if score > 0:
                scored_items.append(
                    (score, item)
                )


        # Highest score first
        scored_items.sort(
            key=lambda x: x[0],
            reverse=True
        )


        return [
            item
            for _, item in scored_items[:top_k]
        ]


    # =====================================================
    # SEARCH BY IS NUMBER
    # =====================================================

    def by_is_number(self, is_num: str):

        cleaned = self.normalize(is_num)

        if not cleaned:
            return []

        results = []

        for standard in self.standards:

            standard_number = self.normalize(
                standard.get(
                    "is_number",
                    standard.get("standard_number", "")
                )
            )

            if cleaned in standard_number:
                results.append(standard)

        return results


# =========================================================
# FORMAT RAG CONTEXT FOR GEMINI
# =========================================================

def format_context(standards_list):

    if not standards_list:
        return "No specific Indian Standard records found in dataset."


    blocks = []

    for item in standards_list:

        standard_number = item.get(
            "is_number",
            item.get("standard_number", "N/A")
        )

        product = item.get(
            "product",
            item.get("title", "N/A")
        )

        category = item.get(
            "category",
            item.get("product_category", "N/A")
        )

        scheme = item.get(
            "scheme",
            "Not specified"
        )

        mandatory = item.get(
            "mandatory",
            item.get("is_mandatory", "Unknown")
        )

        description = item.get(
            "description",
            item.get("scope", "N/A")
        )

        steps = item.get(
            "steps",
            []
        )


        block = (
            f"Standard: {standard_number}\n"
            f"Product: {product}\n"
            f"Category: {category}\n"
            f"Certification Scheme: {scheme}\n"
            f"Mandatory: {mandatory}\n"
            f"Description: {description}"
        )


        if steps:

            if isinstance(steps, list):

                block += "\nCompliance Steps:\n"

                for i, step in enumerate(
                    steps,
                    start=1
                ):
                    block += f"{i}. {step}\n"

            else:

                block += f"\nCompliance Steps: {steps}"


        blocks.append(block)


    return "\n\n------------------------------\n\n".join(blocks)