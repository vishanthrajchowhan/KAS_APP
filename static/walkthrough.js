let mediaRecorder;
let recordedChunks = [];
let recordingTimer;
let autoSnapshotTimer;
let recordingSeconds = 0;
let recordingActive = false;
let videoStream;
let videoElement;
let canvasElement;
let snapshots = [];
let currentFacingMode = "environment";
let speechRecognition;
let speechTranscript = "";
let speechFinalTranscript = "";

const AUTO_SNAPSHOT_SECONDS = 12;

function buildVideoConstraints(facingMode, useExact = false) {
  const facing = useExact ? { exact: facingMode } : { ideal: facingMode };
  return {
    audio: { echoCancellation: true, noiseSuppression: true },
    video: {
      facingMode: facing,
      width: { ideal: 1280 },
      height: { ideal: 720 },
      frameRate: { ideal: 24, max: 30 }
    }
  };
}

async function startCameraStream(preferredFacingMode) {
  const attempts = [
    () => navigator.mediaDevices.getUserMedia(buildVideoConstraints(preferredFacingMode, true)),
    () => navigator.mediaDevices.getUserMedia(buildVideoConstraints(preferredFacingMode, false)),
    () => navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true }, video: true })
  ];

  let lastError = null;
  for (const attempt of attempts) {
    try {
      return await attempt();
    } catch (err) {
      lastError = err;
    }
  }
  throw lastError || new Error("Unable to access camera");
}

function formatTime(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function setWalkthroughStatus(message, tone = "info") {
  const status = document.getElementById("wt-status");
  if (!status) return;
  status.textContent = message;
  status.dataset.tone = tone;
}

function startSpeechCapture() {
  speechTranscript = "";
  speechFinalTranscript = "";
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    setWalkthroughStatus("Recording video. Browser speech capture is not available, so server transcription will be used if configured.", "warning");
    return;
  }

  speechRecognition = new SpeechRecognition();
  speechRecognition.continuous = true;
  speechRecognition.interimResults = true;
  speechRecognition.lang = "en-US";
  speechRecognition.onresult = (event) => {
    let interim = "";
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const text = event.results[i][0].transcript;
      if (event.results[i].isFinal) {
        speechFinalTranscript += `${text.trim()} `;
      } else {
        interim += text;
      }
    }
    speechTranscript = `${speechFinalTranscript} ${interim}`.trim();
  };
  speechRecognition.onerror = () => {};
  speechRecognition.onend = () => {
    if (recordingActive) {
      try { speechRecognition.start(); } catch (err) {}
    }
  };
  try {
    speechRecognition.start();
  } catch (err) {
    setWalkthroughStatus("Video is recording. Browser speech capture could not start.", "warning");
  }
}

function closeWalkthroughModal() {
  const modal = document.getElementById("walkthrough-modal");
  if (recordingActive) stopRecording();
  if (videoStream) videoStream.getTracks().forEach((track) => track.stop());
  if (modal) modal.remove();
  document.body.style.overflow = "";
  document.documentElement.style.overflow = "";
  document.body.classList.remove("wt-modal-open");
}

function createButton(label, className) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.textContent = label;
  return button;
}

async function startRecording(jobId) {
  try {
    if (!navigator.mediaDevices || !window.MediaRecorder) {
      throw new Error("Camera recording is not supported in this browser.");
    }

    const modal = document.createElement("div");
    modal.id = "walkthrough-modal";
    const isCompactMobile = window.matchMedia && window.matchMedia("(max-width: 768px)").matches;
    if (isCompactMobile) modal.classList.add("wt-compact-mobile");

    const header = document.createElement("div");
    header.className = "wt-header";
    const title = document.createElement("div");
    title.className = "wt-title";
    title.textContent = "AI Walkthrough";
    const closeBtn = createButton("Close", "wt-close-btn");
    closeBtn.onclick = closeWalkthroughModal;
    header.appendChild(title);
    header.appendChild(closeBtn);

    videoElement = document.createElement("video");
    videoElement.autoplay = true;
    videoElement.muted = true;
    videoElement.playsInline = true;

    canvasElement = document.createElement("canvas");
    canvasElement.style.display = "none";

    const timerDisplay = document.createElement("div");
    timerDisplay.id = "wt-timer";
    timerDisplay.textContent = "0:00:00";

    const snapshotCount = document.createElement("div");
    snapshotCount.id = "wt-photo-count";
    snapshotCount.textContent = "0 photos";

    const videoContainer = document.createElement("div");
    videoContainer.className = "wt-video-container";
    videoContainer.appendChild(videoElement);
    videoContainer.appendChild(timerDisplay);
    videoContainer.appendChild(snapshotCount);

    const status = document.createElement("div");
    status.id = "wt-status";
    status.textContent = "Start recording, speak clearly, and point the camera at each work area.";

    const controls = document.createElement("div");
    controls.className = "wt-controls";
    const recordBtn = createButton("Record", "wt-control wt-record");
    const snapBtn = createButton("Snap Photo", "wt-control wt-snap");
    const cameraBtn = createButton("Switch Camera", "wt-control wt-camera");
    const doneBtn = createButton("Finish", "wt-control wt-done");
    controls.appendChild(recordBtn);
    controls.appendChild(snapBtn);
    controls.appendChild(cameraBtn);
    controls.appendChild(doneBtn);

    const notesSection = document.createElement("div");
    notesSection.className = "wt-notes";
    const notesLabel = document.createElement("label");
    notesLabel.htmlFor = "wt-notes";
    notesLabel.textContent = "Field notes";
    const notesInput = document.createElement("textarea");
    notesInput.id = "wt-notes";
    notesInput.placeholder = "Optional: type anything the report must include.";
    notesSection.appendChild(notesLabel);
    notesSection.appendChild(notesInput);

    modal.appendChild(header);
    modal.appendChild(videoContainer);
    modal.appendChild(status);
    modal.appendChild(controls);
    modal.appendChild(notesSection);
    modal.appendChild(canvasElement);
    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";
    if (isCompactMobile) document.body.classList.add("wt-modal-open");
    document.body.appendChild(modal);

    currentFacingMode = "environment";
    videoStream = await startCameraStream(currentFacingMode);
    videoElement.srcObject = videoStream;
    await videoElement.play().catch(() => {});

    videoElement.onloadedmetadata = () => {
      if (videoElement.videoWidth && videoElement.videoHeight) {
        videoElement.style.aspectRatio = `${videoElement.videoWidth} / ${videoElement.videoHeight}`;
      }
    };

    cameraBtn.onclick = async () => {
      if (recordingActive) {
        setWalkthroughStatus("Stop recording before switching cameras.", "warning");
        return;
      }
      try {
        currentFacingMode = currentFacingMode === "environment" ? "user" : "environment";
        if (videoStream) videoStream.getTracks().forEach((track) => track.stop());
        videoStream = await startCameraStream(currentFacingMode);
        videoElement.srcObject = videoStream;
        await videoElement.play().catch(() => {});
        setWalkthroughStatus("Camera switched.", "success");
      } catch (err) {
        setWalkthroughStatus(`Unable to switch camera: ${err.message}`, "error");
      }
    };

    const mimeTypes = [
      "video/webm;codecs=vp9,opus",
      "video/webm;codecs=vp8,opus",
      "video/webm"
    ];
    const mimeType = mimeTypes.find((type) => MediaRecorder.isTypeSupported(type)) || "";
    const recorderOptions = mimeType ? { mimeType, bitsPerSecond: 900000 } : { bitsPerSecond: 900000 };

    recordedChunks = [];
    snapshots = [];
    mediaRecorder = new MediaRecorder(videoStream, recorderOptions);
    mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) recordedChunks.push(event.data);
    };

    recordBtn.onclick = () => {
      if (recordingActive) {
        stopRecording();
        recordBtn.textContent = "Record";
        setWalkthroughStatus("Recording stopped. Finish to upload the walkthrough.", "success");
        return;
      }

      recordingSeconds = 0;
      recordedChunks = [];
      snapshots = [];
      snapshotCount.textContent = "0 photos";
      mediaRecorder.start(1000);
      recordingActive = true;
      recordBtn.textContent = "Stop";
      setWalkthroughStatus("Recording. Speak naturally while the app captures photos.", "recording");
      startSpeechCapture();

      takeSnapshot("start");
      recordingTimer = setInterval(() => {
        recordingSeconds += 1;
        timerDisplay.textContent = formatTime(recordingSeconds);
      }, 1000);
      autoSnapshotTimer = setInterval(() => takeSnapshot("auto"), AUTO_SNAPSHOT_SECONDS * 1000);
    };

    snapBtn.onclick = () => takeSnapshot("manual");

    doneBtn.onclick = async () => {
      if (recordingActive) {
        stopRecording();
        await new Promise((resolve) => setTimeout(resolve, 500));
      }
      await uploadWalkthrough(jobId);
    };
  } catch (err) {
    console.warn("Camera/MediaRecorder error:", err);
    const useFallback = confirm("Camera recording is not available in this browser. Upload a recorded video file instead?");
    if (useFallback) openVideoFallback(jobId);
  }
}

function takeSnapshot(source = "manual") {
  if (!videoElement || !canvasElement || !videoElement.videoWidth) {
    setWalkthroughStatus("Camera is not ready for a photo yet.", "warning");
    return;
  }

  canvasElement.width = videoElement.videoWidth;
  canvasElement.height = videoElement.videoHeight;
  const ctx = canvasElement.getContext("2d");
  ctx.drawImage(videoElement, 0, 0);
  canvasElement.toBlob(
    (blob) => {
      if (!blob) return;
      snapshots.push({ blob, timestamp: recordingSeconds, source });
      const count = document.getElementById("wt-photo-count");
      if (count) count.textContent = `${snapshots.length} photo${snapshots.length === 1 ? "" : "s"}`;
      setWalkthroughStatus(`Photo ${snapshots.length} saved at ${formatTime(recordingSeconds)}.`, "success");
    },
    "image/jpeg",
    0.84
  );
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
  }
  recordingActive = false;
  clearInterval(recordingTimer);
  clearInterval(autoSnapshotTimer);
  if (speechRecognition) {
    try { speechRecognition.stop(); } catch (err) {}
  }
}

async function uploadWalkthrough(jobId) {
  if (!recordedChunks.length) {
    setWalkthroughStatus("No video recorded. Press Record first.", "error");
    return;
  }

  try {
    const notesInput = document.getElementById("wt-notes");
    const notes = notesInput ? notesInput.value.trim() : "";
    const blob = new Blob(recordedChunks, { type: recordedChunks[0]?.type || "video/webm" });
    const fd = new FormData();
    fd.append("video", blob, `walk_${Date.now()}.webm`);
    fd.append("job_id", jobId);
    if (notes) fd.append("notes", notes);
    if (speechTranscript) fd.append("browser_transcript", speechTranscript);

    const snapshotTimes = snapshots.map((snapshot) => snapshot.timestamp);
    snapshots.forEach((snapshot, index) => {
      fd.append("snapshots", snapshot.blob, `photo_${String(index + 1).padStart(2, "0")}_${snapshot.timestamp}s.jpg`);
    });
    fd.append("snapshot_times", JSON.stringify(snapshotTimes));

    setWalkthroughStatus("Uploading walkthrough and photos. Keep this tab open.", "recording");
    const res = await fetch("/api/walkthroughs/upload", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Upload failed");

    closeWalkthroughModal();
    window.location.href = `/walkthroughs/${data.id}`;
  } catch (err) {
    setWalkthroughStatus(`Upload failed: ${err.message}`, "error");
    console.error("Upload error:", err);
  }
}

function openVideoFallback(jobId) {
  const fileInput = document.createElement("input");
  fileInput.type = "file";
  fileInput.accept = "video/*";
  fileInput.capture = "environment";
  fileInput.onchange = async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    try {
      const fd = new FormData();
      fd.append("video", file, file.name);
      fd.append("job_id", jobId);
      const res = await fetch("/api/walkthroughs/upload", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Upload failed");
      window.location.href = `/walkthroughs/${data.id}`;
    } catch (err) {
      alert(`Upload failed: ${err.message}`);
    }
  };
  fileInput.click();
}

window.startRecording = startRecording;
window.closeWalkthroughModal = closeWalkthroughModal;
