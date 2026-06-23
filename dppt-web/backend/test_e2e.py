"""
DPPT Web end-to-end test
Verify: create project -> upload outline -> select template -> generate PPTX -> download file
"""

import requests

BASE_URL = "http://localhost:8000"


def test_full_flow():
    # 1. Create project
    r = requests.post(f"{BASE_URL}/api/projects")
    r.raise_for_status()
    project_id = r.json()["id"]
    print(f"[OK] Created project: {project_id}")

    # 2. Upload outline
    outline_text = "Cover\nBackground\nMethods\nResults\nConclusion"
    r = requests.post(
        f"{BASE_URL}/api/projects/{project_id}/outline",
        data={"text": outline_text},
    )
    r.raise_for_status()
    outline = r.json()["outline"]
    print(f"[OK] Parsed outline: {len(outline)} pages")

    # 3. Get templates
    r = requests.post(f"{BASE_URL}/api/projects/{project_id}/templates")
    r.raise_for_status()
    templates = r.json()["templates"]
    template = templates[0]
    print(f"[OK] Got template: {template['name']}")

    # 4. Generate PPTX
    slides = [
        {
            "page_id": p["id"],
            "title": p["title"],
            "body": f"Detailed content for {p['title']}",
            "image": None,
            "layout": "default",
        }
        for p in outline
    ]
    config = {
        "id": project_id,
        "title": outline[0]["title"],
        "outline": outline,
        "template": template,
        "slides": slides,
    }
    r = requests.post(
        f"{BASE_URL}/api/projects/{project_id}/generate",
        json={"config": config},
    )
    r.raise_for_status()
    result = r.json()
    print(f"[OK] Generated: {result['output_path']}")

    # 5. Download file
    r = requests.get(f"{BASE_URL}/api/projects/{project_id}/download")
    r.raise_for_status()
    assert r.headers["content-type"] == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    assert len(r.content) > 0
    print(f"[OK] Downloaded: {len(r.content)} bytes")

    print("\nFull flow verified!")


if __name__ == "__main__":
    test_full_flow()
