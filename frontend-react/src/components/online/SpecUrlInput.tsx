interface SpecUrlInputProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

export function SpecUrlInput({ value, onChange, disabled }: SpecUrlInputProps) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">
        API 文档 URL
      </label>
      <input
        type="url"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        placeholder="输入 OpenAPI/Swagger 文档地址..."
        className="w-full px-4 py-2.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent disabled:opacity-50 disabled:bg-gray-50"
      />
    </div>
  );
}
