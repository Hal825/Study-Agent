import { Check } from 'lucide-react'
import { WORKFLOW_STEPS, type WorkflowStep } from '../../types'

interface StepIndicatorProps {
  currentStep: WorkflowStep
}

export default function StepIndicator({ currentStep }: StepIndicatorProps) {
  const currentIdx = WORKFLOW_STEPS.findIndex((s) => s.key === currentStep)

  return (
    <div className="flex items-center justify-center">
      {WORKFLOW_STEPS.map((step, i) => {
        const done = i < currentIdx
        const active = i === currentIdx

        return (
          <div key={step.key} className="flex items-center">
            {/* Step */}
            <div className="flex flex-col items-center">
              <div
                className={`flex h-7 w-7 items-center justify-center rounded-full text-2xs font-semibold transition-all duration-300 ${
                  done
                    ? 'bg-ink text-white'
                    : active
                      ? 'bg-ink text-white ring-4 ring-gold-100'
                      : 'bg-paper-dark text-ink-muted/40'
                }`}
              >
                {done ? <Check size={11} /> : step.number}
              </div>
              <span
                className={`mt-1 text-2xs font-medium transition-colors whitespace-nowrap ${
                  done ? 'text-ink-soft' : active ? 'text-ink' : 'text-ink-muted/40'
                }`}
              >
                {step.label}
              </span>
            </div>
            {/* Connector */}
            {i < WORKFLOW_STEPS.length - 1 && (
              <div
                className={`mx-2 mb-4 h-px w-8 rounded-full transition-colors duration-500 ${
                  done ? 'bg-ink/30' : 'bg-border'
                }`}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
