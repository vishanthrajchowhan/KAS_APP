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
  }
}

async function startRecording(jobId) {
  try {
    // Create modal container
    const modal = document.createElement('div');
    modal.id = 'walkthrough-modal';
    modal.style.cssText = `
      position: fixed; top: 0; left: 0; 
      width: 100%; height: 100%; 
      background: white; z-index: 9999;
      display: flex; flex-direction: column;
      padding: 0; margin: 0;
    `;

    // Header with close button
    const header = document.createElement('div');
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
      aspect-ratio: 9 / 16;
      background: #000; 
      object-fit: cover;
      flex: 1;
    `;

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
    videoContainer.style.cssText = `
      position: relative; flex: 1;
    `;
    videoContainer.appendChild(videoElement);
    videoContainer.appendChild(timerDisplay);

    // Instructions
    const instructions = document.createElement('div');
    instructions.style.cssText = `
      padding: 12px 16px; background: #f5f5f5; 
      font-size: 13px; color: #666; text-align: center;
    `;
    instructions.textContent = '📸 Take pics and think out loud';

    // Controls area
    const controls = document.createElement('div');
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
    controls.appendChild(doneBtn);

    // Notes area
    const notesSection = document.createElement('div');
    notesSection.style.cssText = `
      padding: 16px; background: white; 
      border-top: 1px solid #ddd; max-height: 200px; 
      overflow-y: auto;
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
    document.body.appendChild(modal);

    // Request camera
    const constraints = { 
      audio: { echoCancellation: true, noiseSuppression: true },
      video: { facingMode: 'environment', width: { ideal: 1280 } }
    };
    videoStream = await navigator.mediaDevices.getUserMedia(constraints);
    videoElement.srcObject = videoStream;

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
    mediaRecorder = new MediaRecorder(videoStream, { mimeType });
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
    alert('Camera error: ' + err.message);
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
    modal.remove();
    
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
