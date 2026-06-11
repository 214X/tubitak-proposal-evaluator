"use client";

import { useMemo, useState } from "react";

import styles from "./sudoku-board.module.css";

type SudokuBoardProps = Readonly<{
  onEngagementChange?: (engaged: boolean) => void;
}>;

const PUZZLE = [
  [5, 3, 0, 0, 7, 0, 0, 0, 0],
  [6, 0, 0, 1, 9, 5, 0, 0, 0],
  [0, 9, 8, 0, 0, 0, 0, 6, 0],
  [8, 0, 0, 0, 6, 0, 0, 0, 3],
  [4, 0, 0, 8, 0, 3, 0, 0, 1],
  [7, 0, 0, 0, 2, 0, 0, 0, 6],
  [0, 6, 0, 0, 0, 0, 2, 8, 0],
  [0, 0, 0, 4, 1, 9, 0, 0, 5],
  [0, 0, 0, 0, 8, 0, 0, 7, 9],
] as const;

const SOLUTION = [
  [5, 3, 4, 6, 7, 8, 9, 1, 2],
  [6, 7, 2, 1, 9, 5, 3, 4, 8],
  [1, 9, 8, 3, 4, 2, 5, 6, 7],
  [8, 5, 9, 7, 6, 1, 4, 2, 3],
  [4, 2, 6, 8, 5, 3, 7, 9, 1],
  [7, 1, 3, 9, 2, 4, 8, 5, 6],
  [9, 6, 1, 5, 3, 7, 2, 8, 4],
  [2, 8, 7, 4, 1, 9, 6, 3, 5],
  [3, 4, 5, 2, 8, 6, 1, 7, 9],
] as const;

type Board = number[][];

export function SudokuBoard({ onEngagementChange }: SudokuBoardProps) {
  const initialBoard = useMemo(() => PUZZLE.map((row) => [...row]), []);
  const [board, setBoard] = useState<Board>(initialBoard);
  const [selectedCell, setSelectedCell] = useState<{ row: number; column: number } | null>(
    null,
  );

  const isSolved = board.every((row, rowIndex) =>
    row.every((value, columnIndex) => value === SOLUTION[rowIndex][columnIndex]),
  );

  function placeValue(nextValue: number) {
    if (!selectedCell) {
      return;
    }

    const { row, column } = selectedCell;

    if (PUZZLE[row][column] !== 0) {
      return;
    }

    setBoard((current) =>
      current.map((row, nextRowIndex) =>
        row.map((cell, nextColumnIndex) => {
          if (nextRowIndex !== selectedCell.row || nextColumnIndex !== selectedCell.column) {
            return cell;
          }

          return nextValue;
        }),
      ),
    );    
  }

  function clearValue() {
    if (!selectedCell) {
      return;
    }

    const { row, column } = selectedCell;

    if (PUZZLE[row][column] !== 0) {
      return;
    }

    setBoard((current) =>
      current.map((currentRow, nextRowIndex) =>
        currentRow.map((cell, nextColumnIndex) => {
          if (nextRowIndex !== row || nextColumnIndex !== column) {
            return cell;
          }

          return 0;
        }),
      ),
    );
  }

  function resetBoard() {
    setBoard(initialBoard.map((row) => [...row]));
    setSelectedCell(null);
    onEngagementChange?.(false);
  }

  return (
    <section
      className={styles.panel}
      aria-labelledby="sudoku-title"
      onFocusCapture={() => onEngagementChange?.(true)}
      onBlurCapture={(event) => {
        const relatedTarget = event.relatedTarget;
        if (!(relatedTarget instanceof Node) || !event.currentTarget.contains(relatedTarget)) {
          onEngagementChange?.(false);
        }
      }}
      onPointerDown={() => onEngagementChange?.(true)}
    >
      <div className={styles.header}>
        <div>
          <p className={styles.eyebrow}>İşlem Devam Ederken</p>
          <h2 id="sudoku-title" className={styles.title}>
            Kısa bir Sudoku molası
          </h2>
        </div>

        <button type="button" className={styles.resetButton} onClick={resetBoard}>
          Yeniden Başlat
        </button>
      </div>

      <p className={styles.description}>
        Değerlendirme süreci zaman zaman birkaç dakika sürebileceği için burada kısa bir
        Sudoku molası sunuluyor. Sayfa yenilenirse oyun başa döner.
      </p>

      <div className={styles.board} role="grid" aria-label="Sudoku tahtası">
        {board.map((row, rowIndex) =>
          row.map((value, columnIndex) => {
            const isFixed = PUZZLE[rowIndex][columnIndex] !== 0;
            const isIncorrect =
              value !== 0 && value !== SOLUTION[rowIndex][columnIndex] && !isFixed;
            const isSelected =
              selectedCell?.row === rowIndex && selectedCell?.column === columnIndex;

            return (
              <button
                type="button"
                key={`${rowIndex}-${columnIndex}`}
                className={`${styles.cell} ${isFixed ? styles.cellFixed : ""} ${
                  isIncorrect ? styles.cellError : ""
                } ${isSelected ? styles.cellSelected : ""} ${
                  selectedCell &&
                  !isSelected &&
                  selectedCell.row === rowIndex &&
                  selectedCell.column !== columnIndex
                    ? styles.cellRelated
                    : ""
                } ${
                  selectedCell &&
                  !isSelected &&
                  selectedCell.column === columnIndex &&
                  selectedCell.row !== rowIndex
                    ? styles.cellRelated
                    : ""
                } ${columnIndex === 2 || columnIndex === 5 ? styles.cellBlockRight : ""} ${
                  rowIndex === 2 || rowIndex === 5 ? styles.cellBlockBottom : ""
                }`}
                onClick={() => setSelectedCell({ row: rowIndex, column: columnIndex })}
              >
                <span className={styles.srOnly}>
                  Satır {rowIndex + 1}, sütun {columnIndex + 1}
                </span>
                <span className={styles.value} aria-invalid={isIncorrect}>
                  {value === 0 ? "" : String(value)}
                </span>
              </button>
            );
          }),
        )}
      </div>

      <div className={styles.keypad}>
        {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((number) => (
          <button
            key={number}
            type="button"
            className={styles.keypadButton}
            onClick={() => placeValue(number)}
            disabled={!selectedCell || PUZZLE[selectedCell.row][selectedCell.column] !== 0}
          >
            {number}
          </button>
        ))}

        <button
          type="button"
          className={`${styles.keypadButton} ${styles.keypadClear}`}
          onClick={clearValue}
          disabled={!selectedCell || PUZZLE[selectedCell.row][selectedCell.column] !== 0}
        >
          Temizle
        </button>
      </div>

      {isSolved ? (
        <p className={`${styles.status} ${styles.statusSolved}`}>
          <span className={styles.statusIcon} aria-hidden="true">
            <CheckIcon />
          </span>
          Sudoku tamamlandı. Oyun sayfanın altında kalmaya devam edecek.
        </p>
      ) : (
        <p className={styles.status} />
      )}
    </section>
  );
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
      <path d="m5 12.5 4.2 4.2L19 7" />
    </svg>
  );
}
