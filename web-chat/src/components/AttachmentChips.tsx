import type { UploadedFile } from '../api'
import { formatBytes } from '../format'
import { useT } from '../i18n'
import {
  canOpenAttachmentDrawer,
  isImageAttachment,
} from '../attachmentPreview'
import { cn } from '@/lib/utils'

export { isImageAttachmentName, isDrawerPreviewableName } from '../attachmentPreview'

// A file selected in the composer, tracked through its upload lifecycle.
export type PendingAttachment = {
  id: string
  name: string
  size: number
  path?: string
  status: 'uploading' | 'done' | 'error'
  error?: string
  /** Object URL (or authenticated content URL) for image hover preview. */
  previewUrl?: string
  /** Platform FileRecord id — required for library file content preview. */
  fileId?: string
  mimeType?: string
}

type PendingProps = {
  items: PendingAttachment[]
  onRemove: (id: string) => void
  /** Called when user clicks a previewable chip that has a fileId. */
  onPreviewDoc?: (item: PendingAttachment) => void
}

type SentPreviewTarget = {
  name: string
  fileId: string
  mimeType?: string
  path?: string
}

type AttachmentListProps = {
  items: UploadedFile[]
  /** User turns align chips with the message bubble (end). */
  align?: 'start' | 'end'
  /** Image / md / pdf with fileId → open FilePreviewDrawer. */
  onPreviewDoc?: (item: SentPreviewTarget) => void
}

/** Editable attachment strip shown above the composer textarea. */
export function PendingAttachments({
  items,
  onRemove,
  onPreviewDoc,
}: PendingProps) {
  const t = useT()
  if (items.length === 0) return null
  return (
    <div className="attach-strip">
      {items.map((a) => {
        const showImagePreview =
          Boolean(a.previewUrl) &&
          isImageAttachment(a.name, {
            mimeType: a.mimeType,
            path: a.path,
          })
        const canDrawerPreview = canOpenAttachmentDrawer(a.name, {
          fileId: a.fileId,
          mimeType: a.mimeType,
          path: a.path,
        })
        return (
          <span
            key={a.id}
            className={`attach-chip attach-${a.status}${
              showImagePreview ? ' attach-chip--image' : ''
            }${canDrawerPreview ? ' attach-chip--doc' : ''}`}
            title={
              a.error ||
              (canDrawerPreview ? t('attach.preview.clickHint') : a.name)
            }
          >
            {showImagePreview && (
              <span className="attach-preview" aria-hidden>
                <img
                  className="attach-preview-img"
                  src={a.previewUrl}
                  alt=""
                />
              </span>
            )}
            {showImagePreview ? (
              <img
                className="attach-chip-thumb"
                src={a.previewUrl}
                alt=""
                aria-hidden
              />
            ) : (
              <span className="attach-icon" aria-hidden>
                📎
              </span>
            )}
            {canDrawerPreview ? (
              <button
                type="button"
                className="attach-name attach-name--preview"
                onClick={() => onPreviewDoc?.(a)}
              >
                {a.name}
              </button>
            ) : (
              <span className="attach-name">{a.name}</span>
            )}
            <span className="attach-size">
              {a.status === 'uploading'
                ? t('attach.uploading')
                : a.status === 'error'
                  ? t('attach.failed')
                  : formatBytes(a.size)}
            </span>
            <button
              type="button"
              className="attach-remove"
              onClick={() => onRemove(a.id)}
              aria-label={t('attach.remove')}
            >
              ×
            </button>
          </span>
        )
      })}
    </div>
  )
}

/** Read-only attachment chips rendered on a sent user turn. */
export function AttachmentList({
  items,
  align = 'start',
  onPreviewDoc,
}: AttachmentListProps) {
  const t = useT()
  if (!items || items.length === 0) return null
  return (
    <div
      data-slot="attachment-list"
      className={cn(
        'attach-strip attach-strip-readonly',
        align === 'end' && 'attach-strip--end',
      )}
    >
      {items.map((a, i) => {
        const showImagePreview =
          Boolean(a.previewUrl) &&
          isImageAttachment(a.name, {
            mimeType: a.mimeType,
            path: a.path,
          })
        const canDrawerPreview = canOpenAttachmentDrawer(a.name, {
          fileId: a.fileId,
          mimeType: a.mimeType,
          path: a.path,
        })
        return (
          <span
            key={`${a.path}-${i}`}
            className={cn(
              'attach-chip attach-done',
              showImagePreview && 'attach-chip--image',
              canDrawerPreview && 'attach-chip--doc',
            )}
            title={
              canDrawerPreview ? t('attach.preview.clickHint') : a.name
            }
          >
            {showImagePreview && (
              <span className="attach-preview" aria-hidden>
                <img
                  className="attach-preview-img"
                  src={a.previewUrl}
                  alt=""
                />
              </span>
            )}
            {showImagePreview ? (
              <img
                className="attach-chip-thumb"
                src={a.previewUrl}
                alt=""
                aria-hidden
              />
            ) : (
              <span className="attach-icon" aria-hidden>
                📎
              </span>
            )}
            {canDrawerPreview && a.fileId ? (
              <button
                type="button"
                className="attach-name attach-name--preview"
                onClick={() =>
                  onPreviewDoc?.({
                    name: a.name,
                    fileId: a.fileId!,
                    mimeType: a.mimeType,
                    path: a.path,
                  })
                }
              >
                {a.name}
              </button>
            ) : (
              <span className="attach-name">{a.name}</span>
            )}
            <span className="attach-size">{formatBytes(a.size)}</span>
          </span>
        )
      })}
    </div>
  )
}
