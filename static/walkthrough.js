// Mobile-friendly AI Walkthrough Recorder with UI feedback
let mediaRecorder;
let recordedChunks = [];
let recordingTimer;
let recordingSeconds = 0;
let recordingActive = false;

function formatTime(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function showWalkthroughStatus(message, type = 'info') {
  const container = document.getElementById('walkthrough-status') || document.createElement('div');
  container.id = 'walkthrough-status';
  container.style.cssText = `
    position: fixed; top: 20px; right: 20px; 
    padding: 12px 16px; border-radius: 4px; 
    font-size: 14px; z-index: 9999;
    background: ${type === 'error' ? '#d32f2f' : type === 'success' ? '#388e3c' : '#1976d2'};
    color: white; box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    max-width: 300px; word-wrap: break-word;
  `;
  container.textContent = message;
  if (!container.parentNode) document.body.appendChild(container);
}

async function startRecording(jobId) {
  try {
    showWalkthroughStatus('📷 Requesting camera access...', 'info');
    
    const constraints = { 
      audio: { echoCancellation: true, noiseSuppression: true },
      video: { facingMode: 'environment', width: { ideal: 1280 } }
    };
    
    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    recordingActive = true;
    recordingSeconds = 0;
    recordedChunks = [];

    // Create preview video element
    const preview = document.createElement('video');
    preview.id = 'walkthrough-preview';
    preview.autoplay = true;
    preview.muted = true;
    preview.playsinline = true;
    preview.srcObject = stream;
    preview.style.cssText = `
      position: fixed; bottom: 20px; right: 20px; 
      width: 200px; height: 150px; 
      background: #000; border-radius: 8px; 
      border: 3px solid #d32f2f; z-index: 9998;
      box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    `;
    document.body.appendChild(preview);

    // Create timer display
    const timerDisplay = document.createElement('div');
    timerDisplay.id = 'walkthrough-timer';
    timerDisplay.style.cssText = `
      position: fixed; bottom: 180px; right: 20px; 
      padding: 8px 12px; background: #d32f2f; color: white;
      border-radius: 4px; font-weight: bold; font-size: 16px;
      z-index: 9998;
    `;
    timerDisplay.textContent = '00:00:00';
    document.body.appendChild(timerDisplay);

    // Create video MIME type with fallback
    let mimeType = 'video/webm';
    if (!MediaRecorder.isTypeSupported('video/webm;codecs=vp9,opus')) {
      if (MediaRecorder.isTypeSupported('video/webm;codecs=vp8,opus')) {
        mimeType = 'video/webm;codecs=vp8,opus';
      } else if (MediaRecorder.isTypeSupported('video/webm')) {
        mimeType = 'video/webm';
      }
    }

    mediaRecorder = new MediaRecorder(stream, { mimeType });
    mediaRecorder.ondataavailable = (e) => { 
      if (e.data && e.data.size > 0) recordedChunks.push(e.data); 
    };
    mediaRecorder.onstop = async () => {
      clearInterval(recordingTimer);
      recordingActive = false;
      
      // Clean up video preview
      stream.getTracks().forEach(track => track.stop());
      preview.remove();
      timerDisplay.remove();

      showWalkthroughStatus('📤 Uploading video (this may take a moment)...', 'info');
      
      const blob = new Blob(recordedChunks, { type: mimeType });
      const fd = new FormData();
      fd.append('video', blob, `walk_${Date.now()}.webm`);
      fd.append('job_id', jobId);
      
      try {
        const res = await fetch('/api/walkthroughs/upload', { method: 'POST', body: fd });
        const data = await res.json();
        
        if (!res.ok) {
          throw new Error(data.error || 'Upload failed');
        }
        
        showWalkthroughStatus(`✅ Walkthrough uploaded! Processing report (ID: ${data.id})...`, 'success');
        console.log('Uploaded walkthrough', data);
        
        // Redirect to view after a moment
        setTimeout(() => {
          window.location.href = `/walkthroughs/${data.id}`;
        }, 2000);
      } catch (err) {
        showWalkthroughStatus(`❌ Upload failed: ${err.message}`, 'error');
        console.error('Upload error:', err);
      }
    };
    
    mediaRecorder.start();
    showWalkthroughStatus('🎥 Recording... Tap "Stop Walkthrough" when done', 'success');
    
    // Start timer
    recordingTimer = setInterval(() => {
      recordingSeconds++;
      timerDisplay.textContent = formatTime(recordingSeconds);
    }, 1000);

  } catch (err) {
    showWalkthroughStatus(`❌ Camera error: ${err.message}`, 'error');
    console.error('Camera access error:', err);
  }
}

function stopRecording() {
  if (!recordingActive || !mediaRecorder) {
    showWalkthroughStatus('⚠️ No active recording', 'info');
    return;
  }
  if (mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
    showWalkthroughStatus('⏸️ Stopping recording...', 'info');
  }
}

// Expose to global for button clicks
window.startRecording = startRecording;
window.stopRecording = stopRecording;
