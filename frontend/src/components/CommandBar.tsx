export function CommandBar() {
  return (
    <div className="cmd">
      <div className="mark">
        <div className="glyph"></div>
        СНАБ <small>единое окно</small>
      </div>
      <div className="search">
        <span className="mono">⌕</span>
        <input placeholder="заявка Т-67, № 1488, поставщик, УПД…" />
      </div>
      <div className="spacer"></div>
      <div className="who">
        <div className="av">—</div>
        <div className="nm">
          <b>Гость</b>
          <span>не авторизован</span>
        </div>
      </div>
    </div>
  )
}
