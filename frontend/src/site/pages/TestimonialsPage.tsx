/**
 * Testimonials page, including the submission form.
 *
 * Only approved and visible reviews are ever fetched, because that is what the
 * public endpoint exposes. A submission is always queued as pending, so the
 * form tells the customer it will be reviewed rather than promising it appears
 * immediately.
 */

import { useState } from 'react'
import type { FormEvent } from 'react'

import { publicApi } from '../api'
import { useAsync } from '@/lib/hooks'
import { TestimonialCard } from '../components/cards'
import { EmptyState, ErrorState, LoadingState } from '../components/primitives'
import { PageIntro } from './ServicesPage'

export function TestimonialsPage() {
  const testimonials = useAsync(() => publicApi.testimonials(), [])
  const items = testimonials.data?.items ?? []

  return (
    <div className="page">
      <div className="shell">
        <PageIntro
          title="Reviews"
          lead="Feedback from guests who have visited the studio. Every review is checked before it appears here."
        />

        {testimonials.loading ? <LoadingState label="Loading reviews" /> : null}
        {testimonials.error !== null ? (
          <ErrorState onRetry={testimonials.reload}>Reviews are unavailable right now.</ErrorState>
        ) : null}
        {testimonials.data !== null && items.length === 0 ? (
          <EmptyState title="No reviews yet">
            Been to us before? We would love to hear how it went.
          </EmptyState>
        ) : null}

        {items.length > 0 ? (
          <div className="grid grid--reviews grid--reviews-wide">
            {items.map((testimonial, index) => (
              <TestimonialCard key={testimonial.id} testimonial={testimonial} index={index} />
            ))}
          </div>
        ) : null}

        <ShareExperience />
      </div>
    </div>
  )
}

function ShareExperience() {
  const [state, setState] = useState<'idle' | 'sending' | 'sent'>('idle')
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)

    const body = {
      customer_name: String(data.get('customer_name') ?? '').trim(),
      content: String(data.get('content') ?? '').trim(),
      rating: Number(data.get('rating') ?? 5),
    }

    // The maximums match the backend exactly, so a legitimate review is never
    // blocked client-side. The minimums are deliberately a little stricter than
    // the backend's, because "A" is not a useful review.
    const problems: Record<string, string> = {}
    if (body.customer_name.length < 2) problems.customer_name = 'Please tell us your name.'
    if (body.content.length < 10) problems.content = 'Please write at least a sentence.'
    if (body.rating < 1 || body.rating > 5) problems.rating = 'Please choose a rating.'
    setFieldErrors(problems)
    if (Object.keys(problems).length > 0) return

    setState('sending')
    setError(null)
    try {
      await publicApi.submitTestimonial(body)
      form.reset()
      setState('sent')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'We could not send that just now.')
      setState('idle')
    }
  }

  if (state === 'sent') {
    return (
      <section className="share share--done" aria-labelledby="share-heading">
        <h2 id="share-heading">Thank you</h2>
        <p>
          Your review has been sent and will appear once we have read it. We appreciate you taking
          the time.
        </p>
        <button type="button" className="link-button" onClick={() => setState('idle')}>
          Write another review
        </button>
      </section>
    )
  }

  return (
    <section className="share" aria-labelledby="share-heading">
      <h2 id="share-heading">Share your experience</h2>
      <p className="share__lead">
        Visited us recently? Tell us how it went — we read every message.
      </p>

      {error !== null ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : null}

      <form className="form" onSubmit={onSubmit} noValidate>
        <div className="form__row">
          <div className="form__field">
            <label htmlFor="customer_name">Your name</label>
            <input
              id="customer_name"
              name="customer_name"
              type="text"
              autoComplete="name"
              maxLength={120}
              required
              aria-invalid={fieldErrors.customer_name !== undefined}
              aria-describedby={fieldErrors.customer_name === undefined ? undefined : 'name-error'}
            />
            {fieldErrors.customer_name !== undefined ? (
              <p className="form-error" id="name-error">
                {fieldErrors.customer_name}
              </p>
            ) : null}
          </div>

          <div className="form__field">
            <label htmlFor="rating">Rating</label>
            <select
              id="rating"
              name="rating"
              defaultValue="5"
              aria-invalid={fieldErrors.rating !== undefined}
              aria-describedby={fieldErrors.rating === undefined ? undefined : 'rating-error'}
            >
              <option value="5">5 — Excellent</option>
              <option value="4">4 — Very good</option>
              <option value="3">3 — Good</option>
              <option value="2">2 — Could be better</option>
              <option value="1">1 — Poor</option>
            </select>
            {fieldErrors.rating !== undefined ? (
              <p className="form-error" id="rating-error">
                {fieldErrors.rating}
              </p>
            ) : null}
          </div>
        </div>

        <div className="form__field">
          <label htmlFor="content">Your review</label>
          <textarea
            id="content"
            name="content"
            rows={4}
            minLength={2}
            maxLength={2000}
            required
            placeholder="What did you have done, and how did you feel about it?"
            aria-invalid={fieldErrors.content !== undefined}
            aria-describedby={fieldErrors.content === undefined ? undefined : 'content-error'}
          />
          {fieldErrors.content !== undefined ? (
            <p className="form-error" id="content-error">
              {fieldErrors.content}
            </p>
          ) : null}
        </div>

        <p className="form__note">Reviews are checked before they appear on this page.</p>

        <button type="submit" className="button button--primary" disabled={state === 'sending'}>
          {state === 'sending' ? 'Sending…' : 'Send my review'}
        </button>
      </form>
    </section>
  )
}
