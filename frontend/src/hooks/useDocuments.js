import { useState } from 'react';
import { useChatContext } from '../context/ChatContext';
import { uploadDocument, deleteDocument } from '../services/api';

export function useDocuments() {
  const { documents, addDocument, removeDocument } = useChatContext();
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);

  async function handleUpload(file) {
    if (!file) return;
    setIsUploading(true);
    setUploadError(null);

    try {
      const result = await uploadDocument(file);
      addDocument({
        id: result.id || 'doc_' + Date.now(),
        filename: file.name,
        status: result.status || 'ready',
        size: `${(file.size / 1024).toFixed(1)} KB`,
      });
    } catch (err) {
      setUploadError(err.message);
    } finally {
      setIsUploading(false);
    }
  }

  async function handleDelete(filename) {
    const pin = window.prompt(`Enter Admin PIN to delete "${filename}":`);
    if (!pin) return;

    try {
      await deleteDocument(filename, pin);
      removeDocument(filename);
    } catch (err) {
      alert(`Deletion failed: ${err.message}`);
    }
  }

  return {
    documents,
    isUploading,
    uploadError,
    handleUpload,
    handleDelete,
  };
}
