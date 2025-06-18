export function normalizeName(name) {
    return name.replace(/[-_.]+/g, "-").toLowerCase();
  }