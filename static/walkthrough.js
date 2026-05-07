// Minimal mobile-friendly recorder for Phase 1 MVP
let mediaRecorder;
let recordedChunks = [];

async function startRecording(jobId) {
  recordedChunks = [];
  const constraints = { audio: true, video: { facingMode: 'environment' } };
  const stream = await navigator.mediaDevices.getUserMedia(constraints);
  const preview = document.createElement('video');
  preview.autoplay = true;
  preview.muted = true;
  preview.srcObject = stream;
  document.body.appendChild(preview);

  mediaRecorder = new MediaRecorder(stream, { mimeType: 'video/webm;codecs=vp9,opus' });
  mediaRecorder.ondataavailable = (e) => { if (e.data && e.data.size) recordedChunks.push(e.data); };
  mediaRecorder.onstop = async () => {
    const blob = new Blob(recordedChunks, { type: 'video/webm' });
    const fd = new FormData();
    fd.append('video', blob, `walk_${Date.now()}.webm`);
    fd.append('job_id', jobId);
    const res = await fetch('/api/walkthroughs/upload', { method: 'POST', body: fd });
    const data = await res.json();
    console.log('Uploaded walkthrough', data);
    alert('Walkthrough uploaded. Processing may take a few minutes.');
    // cleanup
    stream.getTracks().forEach(t => t.stop());
    preview.remove();
  };
  mediaRecorder.start();
  return mediaRecorder;
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop();
}

// Expose to global for simple usage
window.startRecording = startRecording;
window.stopRecording = stopRecording;
