MAAN 06 — Translation, camera and image questions

UPDATE YOUR WORKING MAAN
1. Stop only the MAAN server window with Ctrl+C. Keep Ollama and Tailscale running.
2. Back up your existing MAAN app folder, especially data.
3. Extract this ZIP and copy the CONTENTS of MAAN_HTTPS_v6 into the existing app folder. Replace matching program files. Keep the existing data folder: it contains accounts, chats and the secret key. No user data is included in this ZIP.
4. Double-click SETUP_IMAGE_TRANSLATION.bat once. It runs ollama pull gemma3:4b (about 3.3 GB download). Let it finish. Ollama must be installed, running and connected to the internet for the download. If the command is not found, restart your terminal after installing Ollama.
5. Double-click START_ONLINE.bat. It installs Pillow and the other requirements as needed. Keep the window open.
6. Refresh the website (Ctrl+F5 on laptop). The header shows 06; /api/health reports version 6, public true. Your existing public URL/logins stay the same.

HOW TO USE
Translate text: choose the mode, choose Output language, paste up to 2,000 characters, Send. Source language is detected by the local model.
Ask image: tap Photo or Camera, review the preview, select an answer language, ask a question and Send. Empty question defaults to describing the image.
Read image text: attach a clear close-up of printed text and Send. Unreadable words should be marked [unclear].
Translate image: attach a photo of text, choose the target language, Send. Returns a transcription followed by a translation as text; it does not edit text into the original image.
Camera search: take/upload a photo, review it, Send. The local model produces a short description; that description is sent to web search and shown with the results. It is an object-description search, not a reverse-image matching service. It does not identify people. You can refine the description in Web search mode.
Camera opens the phone's native capture/file interface where supported. Desktop browsers may show a file picker. If the camera option is unavailable, take a photo with the phone's camera app, then use Photo to attach it.
Use Remove photo before sending to discard an attachment. After a completed reply the attachment clears; attach it again for another image question. New chats and opening a saved chat also clear the pending attachment.

LANGUAGES
English, Telugu, Hindi, Tamil, Kannada, Malayalam, Marathi, Bengali, Urdu, Arabic, Spanish, French, German, Japanese, Chinese. These are selectable output languages, not a guarantee of equal model quality. Translation is performed locally by Gemma 3 4B. Test Telugu and your other languages before relying on the results.

PHOTOS / PRIVACY
One photo per request. Browser accepts photos up to 20 MB and resizes to a 1,280-pixel longest edge, converting to JPEG. Server validates JPEG/PNG/WebP, caps decoded bytes/pixels and strips metadata by re-encoding. SVG/PDF and other uploads are not accepted by the server. HEIC support varies; use a JPG or screenshot if decoding fails.
Uploaded photos are sent over your MAAN connection to your host laptop and local Ollama. MAAN does not save photo files or base64 in chat history. Text questions, extracted text, translations and answers ARE saved under the user's account. A photo thumbnail may remain in the current browser conversation until refresh. Camera search sends only the generated text description to the web-search provider, not the photo. Local translation and image Q&A need no paid cloud API.

PERFORMANCE / LIMITS
Gemma 3 4B is larger than the existing qwen3:1.7b chat model. First use and each image request can take minutes on your i7/Iris Xe laptop; no speed guarantee. MAAN unloads the text model before running Gemma and asks Ollama to unload Gemma afterward to reduce memory pressure. Normal chat reloads its model on demand. The existing one-at-a-time queue and account request quotas apply. The browser receives progress messages while Gemma loads. Requests time out rather than waiting indefinitely; long translations may require shorter sections.
Use clear, well-lit close-ups. Small text, handwriting and mixed scripts may be misread. Model instructions ask it to mark uncertainty; outputs still require checking. Camera search can describe the wrong object or return unrelated results. There is no image generation/editing, face identification, persistent image memory, live video feed, or automatic public signup in this version.

TROUBLESHOOTING
Host says image setup needed: run SETUP_IMAGE_TRANSLATION.bat, wait for success, refresh MAAN.
No reply / model error: check Ollama and laptop memory; retry a smaller crop or shorter text. Update Ollama if the model isn't supported.
Port 8080 in use: stop the previous MAAN server; keep Ollama and Tailscale running.
Origin rejected: use START_ONLINE.bat and the exact HTTPS URL it prints.
Rollback: stop MAAN and restore your backup application files, retaining data. The downloaded Gemma model can remain installed.

VALIDATION
Automated tests used simulated Ollama responses, not a downloaded/running Gemma model. Checked all task payloads, threaded streaming, disconnect cleanup, truncation handling, image decoding/limits, model-missing errors, account/origin protection, chat isolation and that camera search forwards text only. Live model accuracy, CPU timing and physical camera capture must be tested on your laptop/phone.

MODEL AND API REFERENCES
https://ollama.com/library/gemma3 (model size, model terms, vision support)
https://docs.ollama.com/capabilities/vision
https://docs.ollama.com/api/chat
https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/capture
