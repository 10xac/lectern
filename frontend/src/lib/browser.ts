/** Leaving the app for another site (an OAuth client's redirect). A seam that tests can replace. */
export const browser = {
  assign: (url: string) => window.location.assign(url),
};
