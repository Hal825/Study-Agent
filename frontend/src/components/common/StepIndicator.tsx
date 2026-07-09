import { Check } from 'lucide-react'
import { WORKFLOW_STEPS, type WorkflowStep } from '../../types'

interface StepIndicatorProps {
  currentStep: WorkflowStep
}

export default function StepIndicator({ currentStep }: StepIndicatorProps) {
  const currentIndex = WORKFLOW_STEPS.findIndex((s) => s.key === currentStep)

  return (
    <div className="flex items-center justify-center gap-0">
      {WORKFLOW_STEPS.map((step, i) => {
        const isCompleted = i < currentIndex
        const isCurrent = i === currentIndex
        const isPending = i > currentIndex

        return (
          <div key={step.key} className="flex items-center">
            {/* Step circle + label */}
            <div className="flex flex-col items-center">
              <div
                className={`flex h-9 w-9 items-center justify-center rounded-full text-sm font-semibold transition-all duration-300 ${
                  isCompleted
                    ? 'bg-primary-600 text-white'
                    : isCurrent
                      ? 'bg-primary-600 text-white ring-4 ring-primary-100'
                      : 'bg-gray-100 text-gray-400'
                }`}
              >
                {isCompleted ? <Check size={15} /> : step.number}
              </div>
              <span
                className={`mt-1.5 text-xs font-medium transition-colors whitespace-nowrap ${
                  isCompleted
                    ? 'text-primary-600'
                    : isCurrent
                      ? 'text-primary-600'
                      : 'text-gray-400'
                }`}
              >
                {step.label}
              </span>
            </div>
            {/* Connector line */}
            {i < WORKFLOW_STEPS.length - 1 && (
              <div
                className={`mx-3 mb-5 h-0.5 w-10 rounded-full transition-colors duration-300 ${
                  isPending ? 'bg-gray-200' : 'bg-primary-400'
                }`}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
