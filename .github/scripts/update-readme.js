const fs = require('fs');
const path = require('path');
const sharp = require('sharp');

const APPS_DIR = 'frontend/src/components/icons/apps';
const README_PATH = 'README.md';
const GRID_START_MARKER = '<!-- START_APP_GRID -->';
const GRID_END_MARKER = '<!-- END_APP_GRID -->';
const ICON_SIZE = 40;
const GRID_COLUMNS = 8;

async function generateAppGrid() {
  const files = fs.readdirSync(APPS_DIR)
    .filter(file => file.endsWith('.svg'))
    .sort();

  const rows = [];
  let currentRow = [];

  for (const file of files) {
    const name = path.basename(file, '.svg')
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');

    currentRow.push(`<img src="frontend/src/components/icons/apps/${file}" alt="${name}" width="${ICON_SIZE}" height="${ICON_SIZE}" />`);

    if (currentRow.length === GRID_COLUMNS) {
      rows.push(currentRow);
      currentRow = [];
    }
  }

  if (currentRow.length > 0) {
    // Center the last row if it's not full
    while (currentRow.length < GRID_COLUMNS) {
      currentRow.push('<img src="" alt="" width="' + ICON_SIZE + '" height="' + ICON_SIZE + '" />');
    }
    rows.push(currentRow);
  }

  return rows;
} 