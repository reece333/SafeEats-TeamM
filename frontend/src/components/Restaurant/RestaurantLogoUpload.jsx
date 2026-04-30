import React, { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../../services/api';

const MAX_SIZE_BYTES = 5 * 1024 * 1024; // 5MB
const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

// Backend returns 1-hour Firebase signed URLs. If the URL expires while the
// page is open we ask the parent to refetch the restaurant so a fresh URL is
// generated server-side. Cap retries so a genuinely broken blob can't loop.
const MAX_IMAGE_LOAD_RETRIES = 1;

const RestaurantLogoUpload = ({
  restaurantId,
  initialLogoUrl,
  onLogoChange,
  onImageError,
}) => {
  const [previewUrl, setPreviewUrl] = useState(initialLogoUrl || '');
  const [error, setError] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isDeleting, setIsDeleting] = useState(false);
  const [hasLoadFailed, setHasLoadFailed] = useState(false);
  const loadRetryCountRef = useRef(0);

  useEffect(() => {
    setPreviewUrl(initialLogoUrl || '');
    // A new URL arriving from the parent (e.g. after a restaurant refetch)
    // means we should give image loading a fresh chance.
    setHasLoadFailed(false);
    loadRetryCountRef.current = 0;
  }, [initialLogoUrl]);

  const handleImageLoadError = useCallback(() => {
    if (loadRetryCountRef.current >= MAX_IMAGE_LOAD_RETRIES) {
      setHasLoadFailed(true);
      return;
    }
    loadRetryCountRef.current += 1;
    if (typeof onImageError === 'function') {
      onImageError();
    } else {
      setHasLoadFailed(true);
    }
  }, [onImageError]);

  const validateFile = (file) => {
    if (!file) {
      return 'No file selected.';
    }

    if (!ACCEPTED_TYPES.includes(file.type)) {
      return 'Please choose a JPEG, PNG, or WebP image.';
    }

    if (file.size > MAX_SIZE_BYTES) {
      return 'Image is too large. Max size is 5MB.';
    }

    return '';
  };

  const performUpload = async (file) => {
    const validationError = validateFile(file);
    if (validationError) {
      setError(validationError);
      return;
    }

    try {
      setError('');
      setIsUploading(true);
      setUploadProgress(0);

      const result = await api.uploadRestaurantLogo(restaurantId, file, (progress) => {
        if (typeof progress === 'number') {
          setUploadProgress(progress);
        }
      });

      const url = result?.logo_url;
      if (url) {
        setPreviewUrl(url);
        if (onLogoChange) {
          onLogoChange({ logo_url: url, logo_path: result?.logo_path || null });
        }
      }
    } catch (e) {
      console.error('Logo upload error:', e);
      setError(
        e?.message ||
          'We could not upload this logo. Please check your connection and try again.'
      );
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  };

  const handleFileInputChange = (event) => {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    performUpload(file);
    // Allow re-selecting the same file
    event.target.value = '';
  };

  const handleDrop = useCallback((event) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDragging(false);

    const file = event.dataTransfer.files && event.dataTransfer.files[0];
    if (!file) return;

    performUpload(file);
  }, []); // performUpload is stable enough for this simple use case

  const handleDragOver = (event) => {
    event.preventDefault();
    event.stopPropagation();
    if (!isDragging) {
      setIsDragging(true);
    }
  };

  const handleDragLeave = (event) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDragging(false);
  };

  const handleDelete = async () => {
    if (!previewUrl) return;

    try {
      setError('');
      setIsDeleting(true);
      await api.deleteRestaurantLogo(restaurantId);
      setPreviewUrl('');
      if (onLogoChange) {
        onLogoChange({ logo_url: null, logo_path: null });
      }
    } catch (e) {
      console.error('Logo delete error:', e);
      setError(
        e?.message ||
          'We could not delete this logo right now. Please try again.'
      );
    } finally {
      setIsDeleting(false);
    }
  };

  const inputId = `restaurant-logo-input-${restaurantId}`;

  return (
    <div className="w-64">
      <label className="block font-medium text-lg mb-2">Restaurant logo</label>

      <div
        className={`border-2 border-dashed rounded-md p-3 text-center cursor-pointer transition ${
          isDragging ? 'border-[#8DB670] bg-green-50' : 'border-gray-300'
        } ${isUploading ? 'opacity-75' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => {
          const input = document.getElementById(inputId);
          if (input) {
            input.click();
          }
        }}
      >
        <input
          id={inputId}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          onChange={handleFileInputChange}
          className="hidden"
        />

        {previewUrl && !hasLoadFailed ? (
          <div className="flex flex-col items-center">
            <img
              src={previewUrl}
              alt="Restaurant logo"
              className="w-32 h-32 object-cover rounded-md mb-2 shadow-sm"
              onError={handleImageLoadError}
            />
            <p className="text-xs text-gray-600 mb-1">
              Tap or drop a new image to replace this logo.
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center text-sm text-gray-600">
            <span className="text-2xl mb-1">🏠</span>
            <p className="font-medium mb-1">
              {hasLoadFailed ? 'Logo unavailable' : 'Drag & drop a logo'}
            </p>
            <p className="text-xs">
              {hasLoadFailed
                ? 'Click to upload a new logo.'
                : <>or <span className="underline">click to browse</span></>}
            </p>
            <p className="mt-2 text-[11px] text-gray-500">
              JPEG, PNG, or WebP, up to 5MB.
            </p>
          </div>
        )}

        {isUploading && (
          <div className="mt-3">
            <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
              <div
                className="bg-[#8DB670] h-2.5 rounded-full transition-all"
                style={{ width: `${uploadProgress || 30}%` }}
              />
            </div>
            <p className="mt-1 text-xs text-gray-600">
              Uploading logo… Please keep this tab open.
            </p>
          </div>
        )}
      </div>

      <div className="mt-2 flex justify-between items-center">
        {previewUrl && (
          <button
            type="button"
            onClick={handleDelete}
            disabled={isDeleting || isUploading}
            className="text-xs text-red-600 hover:text-red-800 disabled:text-gray-400 disabled:cursor-not-allowed"
          >
            {isDeleting ? 'Deleting…' : 'Remove logo'}
          </button>
        )}
      </div>

      {error && (
        <p className="mt-2 text-xs text-red-600">
          {error}
        </p>
      )}
    </div>
  );
};

export default RestaurantLogoUpload;
