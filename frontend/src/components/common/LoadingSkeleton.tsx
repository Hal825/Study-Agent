interface LoadingSkeletonProps {
  lines?: number
}

export default function LoadingSkeleton({ lines = 5 }: LoadingSkeletonProps) {
  return (
    <div className="animate-pulse space-y-4 p-6">
      <div className="h-6 w-3/4 rounded-lg bg-gray-200" />
      <div className="h-4 w-full rounded-lg bg-gray-100" />
      <div className="h-4 w-5/6 rounded-lg bg-gray-100" />
      <div className="h-4 w-2/3 rounded-lg bg-gray-100" />
      {Array.from({ length: lines - 3 }).map((_, i) => (
        <div key={i} className="h-4 w-4/5 rounded-lg bg-gray-100" />
      ))}
    </div>
  )
}
