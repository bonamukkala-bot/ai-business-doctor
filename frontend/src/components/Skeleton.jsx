export default function Skeleton({ className = '', lines = 1 }) {
  return (
    <div className={`skeleton-wrap ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="skeleton-line"
          style={{ width: i === lines - 1 && lines > 1 ? '70%' : '100%' }}
        />
      ))}
    </div>
  )
}
