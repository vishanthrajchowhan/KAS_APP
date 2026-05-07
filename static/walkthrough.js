// CompanyCam-style AI Walkthrough Recorder
let mediaRecorder;
let recordedChunks = [];
let recordingTimer;
let recordingSeconds = 0;
let recordingActive = false;
let videoStream;
let videoElement;
let canvasElement;
let snapshots = [];
let currentFacingMode = 'environment';

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
    } catch (e) {
      lastError = e;
    }
  }
  throw lastError || new Error('Unable to access camera');
}

function formatTime(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function closeWalkthroughModal() {
  const modal = document.getElementById('walkthrough-modal');
  if (modal) {
    if (recordingActive) stopRecording();
    if (videoStream) videoStream.getTracks().forEach(t => t.stop());
    modal.remove();
    try { document.body.style.overflow = ''; document.documentElement.style.overflow = ''; } catch (e) {}
    document.body.classList.remove('wt-modal-open');
  }
}

async function startRecording(jobId) {
  try {
    // Create modal container
    const modal = document.createElement('div');
    modal.id = 'walkthrough-modal';
    const isCompactMobile = window.matchMedia && window.matchMedia('(max-width: 768px)').matches;
    if (isCompactMobile) modal.classList.add('wt-compact-mobile');
    modal.style.cssText = `
      position: fixed; top: 0; left: 0; 
      width: 100%; height: 100%; 
      background: white; z-index: 9999;
      display: flex; flex-direction: column;
      padding: 0; margin: 0;
    `;

    // Header with close button
    const header = document.createElement('div');
    header.className = 'wt-header';
    header.style.cssText = `
      display: flex; justify-content: space-between; align-items: center;
      padding: 12px 16px; background: #2b6cb0; color: white;
      border-bottom: 1px solid #ddd;
    `;
    const title = document.createElement('div');
    title.textContent = '🎥 Walkthrough';
    title.style.fontWeight = 'bold';
    title.style.fontSize = '16px';
    const closeBtn = document.createElement('button');
    closeBtn.textContent = '✕';
    closeBtn.style.cssText = `
      background: none; border: none; color: white; font-size: 24px;
      cursor: pointer; padding: 0; width: 32px; height: 32px;
    `;
    closeBtn.onclick = closeWalkthroughModal;
    header.appendChild(title);
    header.appendChild(closeBtn);

    // Video preview area (full width, responsive)
    videoElement = document.createElement('video');
    videoElement.autoplay = true;
    videoElement.muted = true;
    videoElement.playsinline = true;
    videoElement.style.cssText = `
      width: 100%;
      background: #000;
      object-fit: contain;
      display: block;
      height: 100%;
    `;
    if (!isCompactMobile) {
      videoElement.style.aspectRatio = '9 / 16';
      videoElement.style.flex = '1';
    }

    // Hidden canvas for snapshots
    canvasElement = document.createElement('canvas');
    canvasElement.style.display = 'none';

    // Timer display overlay
    const timerDisplay = document.createElement('div');
    timerDisplay.id = 'wt-timer';
    timerDisplay.style.cssText = `
      position: absolute; top: 60px; right: 16px;
      padding: 10px 14px; background: rgba(211, 47, 47, 0.9); 
      color: white; border-radius: 4px; 
      font-weight: bold; font-size: 18px; font-family: monospace;
      z-index: 10001;
    `;
    timerDisplay.textContent = '00:00:00';

    // Video container
    const videoContainer = document.createElement('div');
    videoContainer.className = 'wt-video-container';
    videoContainer.style.cssText = `
      position: relative; flex: 1 1 auto; min-height: 0;
    `;
    videoContainer.appendChild(videoElement);
    videoContainer.appendChild(timerDisplay);

    // Instructions
    const instructions = document.createElement('div');
    if (isCompactMobile) instructions.classList.add('wt-hide-on-mobile');
    instructions.style.cssText = `
      padding: 12px 16px; background: #f5f5f5; 
      font-size: 13px; color: #666; text-align: center;
    `;
    instructions.textContent = '📸 Take pics and think out loud';

    // Controls area
    const controls = document.createElement('div');
    controls.className = 'wt-controls';
    if (isCompactMobile) controls.classList.add('wt-mobile-controls');
    controls.style.cssText = `
      padding: 12px 16px; background: white;
      display: flex; gap: 8px; justify-content: center;
      flex-wrap: wrap; border-top: 1px solid #ddd;
    `;

    // Record button
    const recordBtn = document.createElement('button');
    recordBtn.id = 'wt-record-btn';
    recordBtn.textContent = '⏺️ Record';
    recordBtn.style.cssText = `
      padding: 10px 20px; background: #d32f2f; color: white;
      border: none; border-radius: 4px; cursor: pointer;
      font-weight: bold; font-size: 14px;
    `;

    // Snap button
    const snapBtn = document.createElement('button');
    snapBtn.id = 'wt-snap-btn';
    snapBtn.textContent = '📷 Snap';
    snapBtn.style.cssText = `
      padding: 10px 20px; background: #2b6cb0; color: white;
      border: none; border-radius: 4px; cursor: pointer;
      font-weight: bold; font-size: 14px;
    `;
    snapBtn.onclick = () => takeSnapshot();

    // Camera switch button
    const cameraBtn = document.createElement('button');
    cameraBtn.id = 'wt-camera-btn';
    cameraBtn.textContent = '🔄 Camera';
    cameraBtn.style.cssText = `
      padding: 10px 14px; background: #6d4c41; color: white;
      border: none; border-radius: 4px; cursor: pointer;
      font-weight: bold; font-size: 14px;
    `;

    // Done button
    const doneBtn = document.createElement('button');
    doneBtn.textContent = '✓ Done';
    doneBtn.style.cssText = `
      padding: 10px 20px; background: #388e3c; color: white;
      border: none; border-radius: 4px; cursor: pointer;
      font-weight: bold; font-size: 14px;
    `;
    doneBtn.onclick = async () => {
      if (recordingActive) stopRecording();
      await uploadWalkthrough(jobId, modal);
    };

    controls.appendChild(recordBtn);
    controls.appendChild(snapBtn);
    controls.appendChild(cameraBtn);
    controls.appendChild(doneBtn);
    if (isCompactMobile) {
      recordBtn.style.minWidth = '96px';
      snapBtn.style.minWidth = '84px';
      cameraBtn.style.minWidth = '92px';
      doneBtn.style.minWidth = '84px';
      recordBtn.style.padding = '9px 12px';
      snapBtn.style.padding = '9px 12px';
      cameraBtn.style.padding = '9px 12px';
      doneBtn.style.padding = '9px 12px';
    }

    // Notes area
    const notesSection = document.createElement('div');
    notesSection.className = 'wt-notes';
    if (isCompactMobile) notesSection.classList.add('wt-hide-on-mobile');
    notesSection.style.cssText = `
      padding: 12px 16px; background: white;
      border-top: 1px solid #ddd; max-height: 160px; overflow-y: auto;
    `;
    const notesLabel = document.createElement('label');
    notesLabel.style.cssText = `
      display: block; font-weight: bold; 
      margin-bottom: 8px; font-size: 13px;
    `;
    notesLabel.textContent = '📝 Notes';
    const notesInput = document.createElement('textarea');
    notesInput.id = 'wt-notes';
    notesInput.placeholder = 'Write down observations, issues, next steps...';
    notesInput.style.cssText = `
      width: 100%; height: 120px; padding: 8px;
      border: 1px solid #ddd; border-radius: 4px;
      font-size: 13px; font-family: inherit;
      resize: vertical;
    `;
    notesSection.appendChild(notesLabel);
    notesSection.appendChild(notesInput);

    // Assemble modal
    modal.appendChild(header);
    modal.appendChild(videoContainer);
    modal.appendChild(instructions);
    modal.appendChild(controls);
    modal.appendChild(notesSection);
    modal.appendChild(canvasElement);
    // Prevent background scrolling while modal is open
    try { document.body.style.overflow = 'hidden'; document.documentElement.style.overflow = 'hidden'; } catch (e) {}
    if (isCompactMobile) document.body.classList.add('wt-modal-open');
    document.body.appendChild(modal);

    // Request camera with robust fallback and preferred rear camera
    currentFacingMode = 'environment';
    videoStream = await startCameraStream(currentFacingMode);
    videoElement.srcObject = videoStream;
    videoElement.onloadedmetadata = () => {
      if (videoElement.videoWidth && videoElement.videoHeight) {
        videoElement.style.aspectRatio = `${videoElement.videoWidth} / ${videoElement.videoHeight}`;
      }
      const track = videoStream && videoStream.getVideoTracks ? videoStream.getVideoTracks()[0] : null;
      const settings = track && track.getSettings ? track.getSettings() : null;
      const activeFacing = settings && settings.facingMode ? settings.facingMode : currentFacingMode;
      videoElement.classList.toggle('wt-user-camera', activeFacing === 'user');
    };

    cameraBtn.onclick = async () => {
      try {
        if (recordingActive) {
          alert('Stop recording before switching camera.');
          return;
        }
        currentFacingMode = currentFacingMode === 'environment' ? 'user' : 'environment';
        if (videoStream) videoStream.getTracks().forEach(t => t.stop());
        videoStream = await startCameraStream(currentFacingMode);
        videoElement.srcObject = videoStream;
      } catch (e) {
        alert('Unable to switch camera: ' + e.message);
      }
    };

    // Setup recording
    let mimeType = 'video/webm';
    if (!MediaRecorder.isTypeSupported('video/webm;codecs=vp9,opus')) {
      if (MediaRecorder.isTypeSupported('video/webm;codecs=vp8,opus')) {
        mimeType = 'video/webm;codecs=vp8,opus';
      } else if (MediaRecorder.isTypeSupported('video/webm')) {
        mimeType = 'video/webm';
      }
    }

    recordedChunks = [];
    snapshots = [];
    // Lower bitrate to reduce upload size and speed up mobile uploads
    const recorderOptions = { mimeType };
    try {
      recorderOptions.bitsPerSecond = 900000; // ~0.9 Mbps
    } catch (e) {
      // ignore
    }
    mediaRecorder = new MediaRecorder(videoStream, recorderOptions);
    mediaRecorder.ondataavailable = (e) => { 
      if (e.data && e.data.size > 0) recordedChunks.push(e.data); 
    };

    recordBtn.onclick = () => {
      if (recordingActive) {
        stopRecording();
        recordBtn.textContent = '⏺️ Record';
      } else {
        recordingSeconds = 0;
        recordedChunks = [];
        mediaRecorder.start();
        recordingActive = true;
        recordBtn.textContent = '⏹️ Stop';
        
        recordingTimer = setInterval(() => {
          recordingSeconds++;
          timerDisplay.textContent = formatTime(recordingSeconds);
        }, 1000);
      }
    };

  } catch (err) {
    // If getUserMedia or MediaRecorder not supported (e.g., some iOS browsers), provide a file-input fallback
    console.warn('Camera/MediaRecorder error:', err);
    const fallback = confirm('Camera recording is not available in this browser. Would you like to upload a recorded video file from your device instead?');
    if (fallback) {
      const fileInput = document.createElement('input');
      fileInput.type = 'file';
      fileInput.accept = 'video/*';
      fileInput.capture = 'environment';
      fileInput.onchange = async (ev) => {
        const file = ev.target.files[0];
        if (!file) return;
        try {
          alert('📤 Uploading selected video...');
          const fd = new FormData();
          fd.append('video', file, file.name);
          fd.append('job_id', jobId);
          const res = await fetch('/api/walkthroughs/upload', { method: 'POST', body: fd });
          const data = await res.json();
          if (!res.ok) throw new Error(data.error || 'Upload failed');
          alert('✅ Walkthrough uploaded via file input. Redirecting...');
          window.location.href = `/walkthroughs/${data.id}`;
        } catch (e) {
          alert('Upload failed: ' + e.message);
        }
      };
      fileInput.click();
    } else {
      alert('Camera error: ' + err.message);
    }
    console.error('Camera access error:', err);
  }
}

function takeSnapshot() {
  if (!videoElement || !canvasElement) return;
  try {
    canvasElement.width = videoElement.videoWidth;
    canvasElement.height = videoElement.videoHeight;
    const ctx = canvasElement.getContext('2d');
    ctx.drawImage(videoElement, 0, 0);
    canvasElement.toBlob((blob) => {
      snapshots.push(blob);
      alert(`📸 Snapshot saved (${snapshots.length})`);
    });
  } catch (err) {
    alert('Snapshot error: ' + err.message);
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
    recordingActive = false;
    clearInterval(recordingTimer);
  }
}

async function uploadWalkthrough(jobId, modal) {
  if (recordedChunks.length === 0) {
    alert('No video recorded. Press Record first.');
    return;
  }

  try {
    const notes = document.getElementById('wt-notes').value;
    const blob = new Blob(recordedChunks, { type: 'video/webm' });
    const fd = new FormData();
    fd.append('video', blob, `walk_${Date.now()}.webm`);
    fd.append('job_id', jobId);
    if (notes) fd.append('notes', notes);

    alert('📤 Uploading walkthrough... this may take a moment');
    const res = await fetch('/api/walkthroughs/upload', { method: 'POST', body: fd });
    const data = await res.json();
    
    if (!res.ok) throw new Error(data.error || 'Upload failed');
    
    // Cleanup
    if (videoStream) videoStream.getTracks().forEach(t => t.stop());
    // Close via helper to restore scrolling
    closeWalkthroughModal();
    
    alert(`✅ Walkthrough uploaded! (ID: ${data.id})\n\nRedirecting to report...`);
    setTimeout(() => {
      window.location.href = `/walkthroughs/${data.id}`;
    }, 1500);
  } catch (err) {
    alert('❌ Upload failed: ' + err.message);
    console.error('Upload error:', err);
  }
}

// Expose to global for button clicks
window.startRecording = startRecording;
window.closeWalkthroughModal = closeWalkthroughModal;
