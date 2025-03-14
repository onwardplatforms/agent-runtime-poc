import { NextRequest, NextResponse } from 'next/server';
import path from 'path';
import fs from 'fs';
import { stat } from 'fs/promises';

/**
 * This route handles serving documents from the .data directory
 * It provides controlled access to documents that are no longer in the public directory
 */
export async function GET(
    request: NextRequest,
    { params }: { params: { path: string[] } }
) {
    try {
        // Join all path parts to create the document path
        const docPath = params.path.join('/');

        // Create the full file path - access from project root
        const filePath = path.join(process.cwd(), '..', '.data', 'documents', docPath);

        // Check if the file exists
        try {
            const stats = await stat(filePath);
            if (!stats.isFile()) {
                return NextResponse.json(
                    { error: 'Not a file' },
                    { status: 400 }
                );
            }
        } catch (e) {
            return NextResponse.json(
                { error: 'File not found' },
                { status: 404 }
            );
        }

        // Read the file and determine its MIME type
        const fileBuffer = fs.readFileSync(filePath);
        const fileExt = path.extname(filePath).toLowerCase();

        // Map file extensions to MIME types
        const mimeTypes: Record<string, string> = {
            '.txt': 'text/plain',
            '.pdf': 'application/pdf',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xls': 'application/vnd.ms-excel',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.csv': 'text/csv',
            '.json': 'application/json',
            '.xml': 'application/xml',
            '.md': 'text/markdown',
        };

        // Get the MIME type or default to octet-stream
        const contentType = mimeTypes[fileExt] || 'application/octet-stream';

        // Return the file with appropriate headers
        return new NextResponse(fileBuffer, {
            headers: {
                'Content-Type': contentType,
                'Content-Disposition': `inline; filename="${path.basename(filePath)}"`,
                'Cache-Control': 'no-cache',
            },
        });
    } catch (error) {
        console.error('Error serving document:', error);
        return NextResponse.json(
            { error: `Error serving document: ${error instanceof Error ? error.message : String(error)}` },
            { status: 500 }
        );
    }
} 