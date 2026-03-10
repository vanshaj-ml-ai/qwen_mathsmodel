@app.post("/chat/image")
async def chat_image(
    file: UploadFile = File(...),
    session_id: str = Form(None)
):
    if not session_id:
        session_id = str(uuid4())

    content = await file.read()
    image_b64 = base64.b64encode(content).decode("utf-8")

    # Step 1: Try VLM extraction
    extracted = extract_question_and_diagram_fallback(image_b64=image_b64)
    qtext = (extracted.get("question_text") or "").strip()
    diag = (extracted.get("diagram_description") or "").strip()

    # Step 2: If VLM failed, use OCR as fallback
    if not qtext:
        import logging
        logging.info("VLM extraction returned empty, falling back to OCR")
        
        suffix = "." + (file.filename.split(".")[-1] if "." in file.filename else "png")
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        
        qtext = (ocr_image(tmp_path) or "").strip()
        
        # Cleanup temp file
        try:
            import os as os_module
            os_module.unlink(tmp_path)
        except:
            pass

    # Step 3: Final validation - if still no question, return error
    if not qtext:
        return {
            "error": True,
            "answer": (
                "I couldn't extract the question from the image. "
                "Please ensure:\n"
                "1. The image is clear and well-lit\n"
                "2. The question text is visible and not cropped\n"
                "3. The image is a standard textbook page or exam paper\n\n"
                "You can also type the question manually for better results."
            ),
            "session_id": session_id
        }

    # Step 4: Generate the answer
    # Load session memory
    session = load_session(session_id)
    chat_context = build_chat_context(session)

    # Generate raw LLM answer
    raw_answer = generate_step_by_step_fallback(
        user_question=qtext,
        book_context="",
        chat_context=chat_context,
        diagram_description=diag
    )

    # CBSE formatted answer
    final_answer = build_final_answer(
        book_context="",
        step_by_step=raw_answer
    )

    # Save formatted answer to session
    update_session(session_id, qtext, final_answer)

    return {
        "error": False,
        "answer": final_answer,
        "session_id": session_id,
        "extracted_question": qtext[:100] + ("..." if len(qtext) > 100 else "")
    }
