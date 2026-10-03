import { useRef, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'

import {
  Badge,
  Banner,
  Button,
  Card,
  Checkbox,
  ConfirmDialog,
  EmptyState,
  Field,
  Modal,
  PageHeader,
  Spinner,
  TextArea,
  TextInput,
} from '@/components/ui'
import { api } from '@/lib/api'
import { useAsync, useMutation } from '@/lib/hooks'
import type { GalleryAdminItem } from '@/types/api'

export function GalleryPage() {
  const list = useAsync(() => api.gallery.list({ limit: 200 }), [])
  const [editing, setEditing] = useState<GalleryAdminItem | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [deleting, setDeleting] = useState<GalleryAdminItem | null>(null)
  const action = useMutation()

  const toggleActive = async (item: GalleryAdminItem) => {
    await action.run(async () => {
      await api.gallery.setActive(item.id, !item.is_active)
      list.reload()
    })
  }

  const move = async (item: GalleryAdminItem, direction: -1 | 1) => {
    const items = list.data?.items ?? []
    const index = items.findIndex((entry) => entry.id === item.id)
    const swap = items[index + direction]
    if (index < 0 || swap === undefined) return

    await action.run(async () => {
      await api.gallery.reorder({
        items: [
          { id: item.id, display_order: swap.display_order },
          { id: swap.id, display_order: item.display_order },
        ],
      })
      list.reload()
    })
  }

  const confirmDelete = async () => {
    if (deleting === null) return
    const ok = await action.run(async () => {
      // Deletes the S3 object and the record together.
      await api.media.remove(deleting.id)
      list.reload()
    })
    if (ok) setDeleting(null)
  }

  return (
    <>
      <PageHeader
        title="Gallery & media"
        description="Upload images to storage and curate what appears in previous work."
        actions={
          <>
            <Button
              variant="secondary"
              onClick={() => {
                setEditing(null)
                setFormOpen(true)
              }}
              disabled={action.busy}
            >
              Add by URL
            </Button>
            <Button onClick={() => setUploadOpen(true)} disabled={action.busy}>
              Upload image
            </Button>
          </>
        }
      />

      {action.error !== null && (
        <Banner tone="error" onDismiss={action.clear}>
          {action.error}
        </Banner>
      )}

      <Card>
        {list.loading ? (
          <Spinner label="Loading gallery" />
        ) : list.error !== null ? (
          <Banner tone="error">{list.error}</Banner>
        ) : (list.data?.items.length ?? 0) === 0 ? (
          <EmptyState
            title="No images yet"
            description="Upload a photo of your work to get started."
            action={<Button onClick={() => setUploadOpen(true)}>Upload image</Button>}
          />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Image</th>
                  <th>Title</th>
                  <th>Category</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(list.data?.items ?? []).map((item, index, all) => (
                  <tr key={item.id}>
                    <td>
                      <div className="row" style={{ flexWrap: 'nowrap', gap: '2px' }}>
                        <Button
                          variant="ghost"
                          className="btn--small"
                          disabled={index === 0 || action.busy}
                          onClick={() => move(item, -1)}
                          aria-label={`Move ${item.title} up`}
                        >
                          ↑
                        </Button>
                        <Button
                          variant="ghost"
                          className="btn--small"
                          disabled={index === all.length - 1 || action.busy}
                          onClick={() => move(item, 1)}
                          aria-label={`Move ${item.title} down`}
                        >
                          ↓
                        </Button>
                      </div>
                    </td>
                    <td>
                      <img
                        className="thumb"
                        src={item.image_url}
                        alt={item.title}
                        loading="lazy"
                      />
                    </td>
                    <td>
                      <div className="cell-title">{item.title}</div>
                      {item.file_size !== null && item.file_size !== undefined && (
                        <div className="cell-sub">{Math.round(item.file_size / 1024)} KB</div>
                      )}
                    </td>
                    <td>{item.category ?? '—'}</td>
                    <td>
                      <Badge tone={item.is_active ? 'success' : 'neutral'}>
                        {item.is_active ? 'Visible' : 'Hidden'}
                      </Badge>
                    </td>
                    <td className="actions">
                      <Button
                        variant="secondary"
                        className="btn--small"
                        onClick={() => {
                          setEditing(item)
                          setFormOpen(true)
                        }}
                      >
                        Edit
                      </Button>
                      <Button
                        variant="ghost"
                        className="btn--small"
                        onClick={() => toggleActive(item)}
                        disabled={action.busy}
                      >
                        {item.is_active ? 'Hide' : 'Show'}
                      </Button>
                      <Button
                        variant="ghost"
                        className="btn--small"
                        onClick={() => setDeleting(item)}
                      >
                        Delete
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {uploadOpen && (
        <UploadDialog
          onClose={() => setUploadOpen(false)}
          onSaved={() => {
            setUploadOpen(false)
            list.reload()
          }}
        />
      )}

      {formOpen && (
        <GalleryForm
          item={editing}
          onClose={() => setFormOpen(false)}
          onSaved={() => {
            setFormOpen(false)
            list.reload()
          }}
        />
      )}

      {deleting !== null && (
        <ConfirmDialog
          title="Delete image"
          message={`Delete "${deleting.title}"? The stored file is removed too. This cannot be undone.`}
          busy={action.busy}
          onCancel={() => setDeleting(null)}
          onConfirm={confirmDelete}
        />
      )}
    </>
  )
}

function UploadDialog({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('gallery')
  const { busy, error, run } = useMutation()
  const input = useRef<HTMLInputElement>(null)

  const onPick = (event: ChangeEvent<HTMLInputElement>) => {
    const picked = event.target.files?.[0] ?? null
    setFile(picked)
    // Default the title to the filename so the form is usable immediately.
    if (picked !== null && title === '') setTitle(picked.name.replace(/\.[^.]+$/, ''))
  }

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (file === null) return
    const fields: Record<string, string> = { title: title.trim(), category }
    if (description.trim() !== '') fields.description = description.trim()

    const ok = await run(() => api.media.upload(file, fields))
    if (ok) onSaved()
  }

  return (
    <Modal
      title="Upload image"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" form="upload-form" busy={busy} disabled={busy || file === null}>
            Upload
          </Button>
        </>
      }
    >
      <form id="upload-form" onSubmit={onSubmit} className="stack">
        {error !== null && <Banner tone="error">{error}</Banner>}

        <Field label="File" hint="JPEG, PNG or WebP, up to 5 MB.">
          {(id) => (
            <input
              ref={input}
              id={id}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={onPick}
              required
            />
          )}
        </Field>

        {file !== null && (
          <img
            className="thumb"
            style={{ width: 120, height: 120 }}
            src={URL.createObjectURL(file)}
            alt="Selected preview"
          />
        )}

        <Field label="Title">
          {(id) => (
            <TextInput
              id={id}
              value={title}
              onChange={setTitle}
              required
              maxLength={160}
            />
          )}
        </Field>

        <Field label="Description">
          {(id) => (
            <TextArea
              id={id}
              value={description}
              onChange={setDescription}
              maxLength={1000}
            />
          )}
        </Field>

        <Field label="Category" hint="Storage category, e.g. gallery or general.">
          {(id) => (
            <TextInput
              id={id}
              value={category}
              onChange={setCategory}
              maxLength={80}
            />
          )}
        </Field>
      </form>
    </Modal>
  )
}

interface GalleryFormState {
  title: string
  description: string
  image_url: string
  category: string
  is_active: boolean
}

function GalleryForm({
  item,
  onClose,
  onSaved,
}: {
  item: GalleryAdminItem | null
  onClose: () => void
  onSaved: () => void
}) {
  const [form, setForm] = useState<GalleryFormState>(() => ({
    title: item?.title ?? '',
    description: item?.description ?? '',
    image_url: item?.image_url ?? '',
    category: item?.category ?? '',
    is_active: item?.is_active ?? true,
  }))
  const { busy, error, run } = useMutation()

  const set = <K extends keyof GalleryFormState>(key: K, value: GalleryFormState[K]) =>
    setForm((current) => ({ ...current, [key]: value }))

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault()
    const payload = {
      title: form.title.trim(),
      description: form.description.trim() || null,
      image_url: form.image_url.trim(),
      category: form.category.trim() || null,
      is_active: form.is_active,
    }
    const ok = await run(() =>
      item === null ? api.gallery.create(payload) : api.gallery.update(item.id, payload),
    )
    if (ok) onSaved()
  }

  return (
    <Modal
      title={item === null ? 'Add image by URL' : `Edit ${item.title}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" form="gallery-form" busy={busy} disabled={busy}>
            Save
          </Button>
        </>
      }
    >
      <form id="gallery-form" onSubmit={onSubmit} className="stack">
        {error !== null && <Banner tone="error">{error}</Banner>}

        <Field label="Title">
          {(id) => (
            <TextInput
              id={id}
              value={form.title}
              onChange={(value) => set('title', value)}
              required
              maxLength={160}
            />
          )}
        </Field>

        <Field
          label="Image URL"
          hint={
            item?.s3_key
              ? 'This item is backed by an uploaded file. Changing the URL detaches it from that file.'
              : 'Use an https URL. Upload a new file to store it yourself.'
          }
        >
          {(id) => (
            <TextInput
              id={id}
              type="url"
              value={form.image_url}
              onChange={(value) => set('image_url', value)}
              required
            />
          )}
        </Field>

        {form.image_url !== '' && (
          <img className="thumb" style={{ width: 120, height: 120 }} src={form.image_url} alt="Preview" />
        )}

        <Field label="Description">
          {(id) => (
            <TextArea
              id={id}
              value={form.description}
              onChange={(value) => set('description', value)}
              maxLength={1000}
            />
          )}
        </Field>

        <Field label="Category" hint="Display grouping, e.g. Bridal.">
          {(id) => (
            <TextInput
              id={id}
              value={form.category}
              onChange={(value) => set('category', value)}
              maxLength={80}
            />
          )}
        </Field>

        <Checkbox
          checked={form.is_active}
          onChange={(value) => set('is_active', value)}
          label="Visible on the public website"
        />
      </form>
    </Modal>
  )
}
