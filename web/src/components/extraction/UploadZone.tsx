"use client";

import { useCallback, useState, useRef } from "react";
import { cn, formatBytes } from "@/lib/utils";

interface UploadZoneProps {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
}

export function UploadZone({ onFileSelected, disabled }: UploadZoneProps) {
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateFile = useCallback((file: File): boolean => {
    setError(null);
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Only PDF files are accepted");
      return false;
    }
    if (file.size > 100 * 1024 * 1024) {
      setError("File too large (max 100 MB)");
      return false;
    }
    if (file.size === 0) {
      setError("File is empty");
      return false;
    }
    return true;
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      if (disabled) return;

      const file = e.dataTransfer.files[0];
      if (file && validateFile(file)) {
        onFileSelected(file);
      }
    },
    [disabled, onFileSelected, validateFile]
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file && validateFile(file)) {
        onFileSelected(file);
      }
      // Reset input so same file can be re-selected
      e.target.value = "";
    },
    [onFileSelected, validateFile]
  );

  return (
    <div>
      <div
        onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => !disabled && inputRef.current?.click()}
        className={cn(
          "relative border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-all duration-200",
          disabled
            ? "border-neutral-200 bg-neutral-50 cursor-not-allowed opacity-60"
            : dragOver
              ? "border-brand-primary bg-sky-50 drop-zone-active"
              : "border-neutral-300 hover:border-brand-primary hover:bg-sky-50/30"
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          onChange={handleFileInput}
          disabled={disabled}
          className="hidden"
        />

        {/* Upload icon */}
        <div className="flex justify-center mb-4">
          <div className={cn(
            "w-14 h-14 rounded-2xl flex items-center justify-center",
            dragOver ? "bg-brand-primary text-white" : "bg-neutral-100 text-neutral-400"
          )}>
            <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m6.75 12l-3-3m0 0l-3 3m3-3v6m-1.5-15H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
            </svg>
          </div>
        </div>

        <p className="text-sm font-medium text-neutral-700 mb-1">
          {dragOver ? "Drop your protocol here" : "Upload Protocol PDF"}
        </p>
        <p className="text-xs text-neutral-400">
          Drag and drop or click to browse. PDF only, max 100 MB.
        </p>
      </div>

      {error && (
        <div className="mt-3 flex items-center gap-2 text-sm text-red-600 bg-red-50 rounded-lg px-4 py-2.5">
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
          </svg>
          {error}
        </div>
      )}
    </div>
  );
}
