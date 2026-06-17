import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "OCR Document Extractor",
  description:
    "Interactive OCR extraction tool for Vietnamese documents — ID cards, invoices, and more. Upload a document to extract structured data with visual bounding box highlighting.",
  keywords: ["OCR", "document extraction", "Vietnamese ID card", "invoice", "PaddleOCR"],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col bg-gray-950 text-white">
        {children}
      </body>
    </html>
  );
}
