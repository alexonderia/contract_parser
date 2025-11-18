import type {
  SpecificationAnchor,
  SpecificationResponse,
  SpecificationTable,
  DocumentSection,
} from "../api/specification";

interface AnchorProps {
  title: string;
  anchor: SpecificationAnchor;
}

function AnchorPreview({ title, anchor }: AnchorProps) {
  const typeLabel = anchor.type === "table" ? "Таблица" : "Параграф";
  return (
    <div className="specification-preview__anchor">
      <span className="specification-preview__anchor-label">{title}</span>
      <span className="specification-preview__anchor-value">
        #{anchor.index + 1} · {typeLabel} — {anchor.preview || "(пусто)"}
      </span>
    </div>
  );
}

interface TableProps {
  table: SpecificationTable;
  order: number;
}

function SpecificationTablePreview({ table, order }: TableProps) {
  return (
    <div className="specification-table">
      <header className="specification-table__header">
        <div className="specification-table__title">
          Таблица {order + 1} · #{table.index}
        </div>
        <div className="specification-table__meta">
          {table.row_count} строк · {table.column_count} столбцов
        </div>
        <div className="specification-table__anchors">
          <span>
            ↳ начало — #{table.start_anchor.index} ({table.start_anchor.type})
          </span>
          <span>
            ↳ конец — #{table.end_anchor.index} ({table.end_anchor.type})
          </span>
        </div>
      </header>
      {table.rows.length > 0 ? (
        <div className="specification-table__scroll">
          <table className="specification-table__table">
            <tbody>
              {table.rows.map((row, rowIndex) => (
                <tr key={`${table.index}-${rowIndex}`}>
                  {row.map((cell, cellIndex) => {
                    const raw = cell ?? "";
                    const content = raw.trim() || "\u00A0";
                    if (rowIndex === 0) {
                      return (
                        <th key={`${table.index}-${rowIndex}-${cellIndex}`}>{content}</th>
                      );
                    }
                    return (
                      <td key={`${table.index}-${rowIndex}-${cellIndex}`}>{content}</td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="specification-table__empty">Таблица не содержит данных</p>
      )}
    </div>
  );
}

interface Props {
  filename: string;
  specification: SpecificationResponse;
  exportedJsonName?: string | null;
  exportedJsonBase64?: string | null;
  sections?: DocumentSection[];
}

function downloadBase64File(base64: string, filename: string) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  const blob = new Blob([bytes], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export default function SpecificationPreview({
  filename,
  specification,
  exportedJsonName,
  exportedJsonBase64,
  sections,
}: Props) {
  return (
    <div className="specification-preview">
      <div className="specification-preview__header">
        <p className="specification-preview__document">📎 Документ «{filename}»</p>
        <p className="specification-preview__heading">Заголовок: {specification.heading}</p>
        {exportedJsonBase64 && exportedJsonName ? (
          <button
            type="button"
            className="button specification-preview__download"
            onClick={() => downloadBase64File(exportedJsonBase64, exportedJsonName)}
          >
            Скачать спецификацию (JSON)
          </button>
        ) : null}
      </div>
      {sections && sections.length > 0 ? (
        <div className="specification-preview__sections">
          <h4 className="specification-preview__sections-title">Разделы документа</h4>
          <ul className="specification-preview__section-list">
            {sections.map((section) => (
              <li key={`${section.filename}-${section.number ?? "header"}`}>
                <div className="specification-preview__section-title">
                  {section.number !== null ? `${section.number}. ` : "Шапка: "}
                  {section.title}
                  <span className="specification-preview__section-filename"> · {section.filename}</span>
                </div>
                <p className="specification-preview__section-content">{section.content || "(раздел пуст)"}</p>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <div className="specification-preview__anchors">
        <AnchorPreview title="Начало" anchor={specification.start_anchor} />
        <AnchorPreview title="Конец" anchor={specification.end_anchor} />
      </div>
      <div className="specification-preview__tables">
        {specification.tables.length === 0 ? (
          <p className="specification-preview__empty">В разделе не найдено таблиц.</p>
        ) : (
          specification.tables.map((table, idx) => (
            <SpecificationTablePreview key={table.index} table={table} order={idx} />
          ))
        )}
      </div>
    </div>
  );
}