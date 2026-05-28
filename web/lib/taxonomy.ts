import rawTaxonomy from "./_generated/taxonomy.json";

export type Category = {
  type_id: number;
  slug: string;
  name: string;
  sort: number;
};

export type Badge = {
  code: string;
  slug: string;
  name: string;
  sort: number;
  home_entry?: boolean;
};

export type TagGroup = "format" | "cuisine" | "occasion" | "feature";

export type Tag = {
  code: string;
  slug: string;
  name: string;
  group: TagGroup;
};

export const categories: Category[] = (rawTaxonomy.categories as Category[])
  .slice()
  .sort((a, b) => a.sort - b.sort);

export const badges: Badge[] = rawTaxonomy.badges as Badge[];
export const tags: Tag[] = rawTaxonomy.tags as Tag[];

export function getCategoryBySlug(slug: string): Category | undefined {
  return categories.find((c) => c.slug === slug);
}

export function getCategoryByTypeId(typeId: number): Category | undefined {
  return categories.find((c) => c.type_id === typeId);
}

export function getSlugByTypeId(typeId: number): string | null {
  return categories.find((c) => c.type_id === typeId)?.slug ?? null;
}

export function getTagsByGroup(group: TagGroup): Tag[] {
  return tags.filter((t) => t.group === group);
}

export const premiumBadge: Badge | undefined = badges.find((b) => b.home_entry);
