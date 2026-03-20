export function uploadFileWithProgress(
  file: File,
  onProgress: (percent: number) => void
) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    const formData = new FormData();
    formData.append("file", file);

    xhr.open("POST", "http://127.0.0.1:8000/upload");

    // 🔥 TRACK PROGRESS
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        const percent = Math.round((event.loaded / event.total) * 100);
        onProgress(percent);
      }
    };

    xhr.onload = () => {
      if (xhr.status === 200) {
        resolve(JSON.parse(xhr.response));
      } else {
        reject("Upload failed");
      }
    };

    xhr.onerror = () => reject("Network error");

    xhr.send(formData);
  });
}