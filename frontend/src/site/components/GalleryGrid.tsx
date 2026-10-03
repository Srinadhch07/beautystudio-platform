/**
 * Gallery grid and lightbox.
 *
 * The grid is a plain list of real buttons, so it is keyboard navigable for free.
 * The lightbox is a modal dialog with focus moved in on open, Escape to close,
 * arrow keys to move between images, and scroll locked while it is up.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import type { PublicGalleryItem } from '../types'
import { CmsImage } from './primitives'

export function GalleryGrid({
  items,
  columns = 3,
}: {
  items: PublicGalleryItem[]
  columns?: 2 | 3 | 4
}) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null)
  const closeRef = useRef<HTMLButtonElement>(null)

  const close = useCallback(() => setActiveIndex(null), [])

  const step = useCallback(
    (delta: number) => {
      setActiveIndex((current) => {
        if (current === null || items.length === 0) return current
        return (current + delta + items.length) % items.length
      })
    },
    [items.length],
  )

  useEffect(() => {
    if (activeIndex === null) return
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeRef.current?.focus()

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        close()
      } else if (event.key === 'ArrowRight') {
        event.preventDefault()
        step(1)
      } else if (event.key === 'ArrowLeft') {
        event.preventDefault()
        step(-1)
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.body.style.overflow = previous
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [activeIndex, close, step])

  if (items.length === 0) return null
  const active = activeIndex === null ? null : items[activeIndex]

  return (
    <>
      <ul className={`gallery-grid gallery-grid--${columns}`}>
        {items.map((item, index) => (
          <li key={item.id}>
            <button
              type="button"
              className="gallery-grid__item"
              onClick={() => setActiveIndex(index)}
              aria-label={`View larger: ${item.title}`}
            >
              <CmsImage src={item.image_url} alt={item.title} ratio="1 / 1" />
            </button>
          </li>
        ))}
      </ul>

      {active !== null && activeIndex !== null ? (
        <div
          className="lightbox"
          role="dialog"
          aria-modal="true"
          aria-label={active.title}
          onClick={(event) => {
            if (event.target === event.currentTarget) close()
          }}
        >
          <button ref={closeRef} type="button" className="lightbox__close" onClick={close}>
            <span className="sr-only">Close image</span>
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>

          {items.length > 1 ? (
            <>
              <button
                type="button"
                className="lightbox__nav lightbox__nav--prev"
                onClick={() => step(-1)}
              >
                <span className="sr-only">Previous image</span>
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
                  <path d="M15 5l-7 7 7 7" />
                </svg>
              </button>
              <button
                type="button"
                className="lightbox__nav lightbox__nav--next"
                onClick={() => step(1)}
              >
                <span className="sr-only">Next image</span>
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
                  <path d="M9 5l7 7-7 7" />
                </svg>
              </button>
            </>
          ) : null}

          <figure className="lightbox__figure">
            <img src={active.image_url} alt={active.title} />
            <figcaption>
              <strong>{active.title}</strong>
              {active.description ? <span>{active.description}</span> : null}
            </figcaption>
          </figure>
        </div>
      ) : null}
    </>
  )
}
