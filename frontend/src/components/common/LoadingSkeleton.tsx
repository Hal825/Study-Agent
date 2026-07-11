interface LoadingSkeletonProps {
  lines?: number
}

export default function LoadingSkeleton({ lines = 5 }: LoadingSkeletonProps) {
  return (
    <div className="animate-fade-in space-y-3 py-4">
      <div className="h-4 w-1/3 animate-pulse rounded-full bg-paper-dark" />
      {Array.from({ length: lines - 1 }).map((_, i) => (
        <div
          key={i}
          className="h-3 animate-pulse rounded-full bg-paper-dark"
          style={{ width: `${50 + Math.random() * 50}%` }}
        />
      ))}
    </div>
  )
}
