import { useState, useCallback, useRef, type DragEvent } from 'react';
import { Upload, FileJson, AlertCircle } from 'lucide-react';

interface FileDropZoneProps {
  onFile: (file: File) => void;
  isLoading?: boolean;
  accept?: string;
}

export function FileDropZone({ onFile, isLoading, accept = '.json,application/json' }: FileDropZoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateAndLoad = useCallback(
    (file: File) => {
      setError(null);
      if (!file.name.endsWith('.json') && file.type !== 'application/json') {
        setError('请选择 JSON 格式的报告文件');
        return;
      }
      if (file.size > 50 * 1024 * 1024) {
        setError('文件大小不能超过 50MB');
        return;
      }
      setFileName(file.name);
      onFile(file);
    },
    [onFile],
  );

  const handleDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) validateAndLoad(file);
    },
    [validateAndLoad],
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) validateAndLoad(file);
    },
    [validateAndLoad],
  );

  return (
    <div>
      <div
        onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
          isDragOver
            ? 'border-indigo-400 bg-indigo-50'
            : 'border-gray-300 hover:border-gray-400 bg-white'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          onChange={handleChange}
          className="hidden"
        />

        {isLoading ? (
          <div className="flex flex-col items-center gap-2">
            <div className="w-8 h-8 border-3 border-indigo-200 border-t-indigo-500 rounded-full animate-spin" />
            <p className="text-sm text-gray-500">正在解析文件...</p>
          </div>
        ) : fileName ? (
          <div className="flex flex-col items-center gap-2">
            <FileJson className="w-10 h-10 text-indigo-500" />
            <p className="text-sm font-medium text-gray-700">{fileName}</p>
            <p className="text-xs text-gray-400">点击重新选择</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <Upload className="w-10 h-10 text-gray-400" />
            <p className="text-sm font-medium text-gray-600">点击或拖拽 JSON 报告文件到此处</p>
            <p className="text-xs text-gray-400">支持 report_*.json 格式，最大 50MB</p>
          </div>
        )}
      </div>

      {error && (
        <div className="flex items-center gap-2 mt-2 text-red-600 text-sm">
          <AlertCircle className="w-4 h-4" />
          {error}
        </div>
      )}
    </div>
  );
}
