import React, { useRef, useState } from 'react';
import { useDocuments } from '../../hooks/useDocuments';

export function DocumentUpload() {
  const { handleUpload, isUploading, uploadError } = useDocuments();
  const fileInputRef = useRef(null);
  const [isDragOver, setIsDragOver] = useState(false);

  function onFileChange(e) {
    const file = e.target.files?.[0];
    if (file) {
      handleUpload(file);
      e.target.value = '';
    }
  }

  function onDrop(e) {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      handleUpload(file);
    }
  }

  return (
    <div>
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.txt,.md"
        style={{ display: 'none' }}
        onChange={onFileChange}
      />
      <div
        className="upload-dropzone"
        style={{ borderColor: isDragOver ? 'var(--text-primary)' : undefined }}
        onClick={() => fileInputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragOver(true);
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={onDrop}
      >
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ margin: '0 auto' }}>
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
          <polyline points="17 8 12 3 7 8"></polyline>
          <line x1="12" y1="3" x2="12" y2="15"></line>
        </svg>
        <p>{isUploading ? 'Uploading & Ingesting...' : 'Upload PDF, Markdown, or Plain Text'}</p>
        <span>Drag & drop or click to browse</span>
      </div>
      {uploadError && (
        <div style={{ color: '#ef4444', fontSize: '11px', marginTop: '6px' }}>
          {uploadError}
        </div>
      )}
    </div>
  );
}
