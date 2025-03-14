"use client";

import { useState, useRef, useEffect } from "react";
import { PlusIcon, FilePlus2Icon } from "lucide-react";

type FileUploadProps = {
    onFileSelect: (files: File[]) => void;
    disabled?: boolean;
};

export function FileUpload({ onFileSelect, disabled = false }: FileUploadProps) {
    const [showMenu, setShowMenu] = useState(false);
    const [showTooltip, setShowTooltip] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const menuRef = useRef<HTMLDivElement>(null);
    const buttonRef = useRef<HTMLButtonElement>(null);
    const [debugMode, setDebugMode] = useState(false);

    const handleButtonClick = () => {
        if (disabled) return;
        console.log("Upload button clicked, showing menu");
        setShowMenu(!showMenu);
    };

    const handleUploadClick = () => {
        console.log("'Upload from computer' option clicked");
        // We no longer need to manually click the file input
        // It will be clicked directly by the user via the transparent overlay
        console.log("Upload option ready for file selection");
    };

    const handleDirectFileInputClick = () => {
        console.log("Direct file input clicked");
    };

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        console.log("File input changed event fired", e);
        console.log("Files selected:", e.target.files);

        if (e.target.files && e.target.files.length > 0) {
            const filesArray = Array.from(e.target.files);
            console.log("Calling onFileSelect with files:", filesArray.map(f => f.name));
            onFileSelect(filesArray);

            // Reset the file input so the same file can be selected again
            if (fileInputRef.current) {
                fileInputRef.current.value = "";
            }
        } else {
            console.log("No files selected in file input");
        }

        // Close the menu after selection
        setShowMenu(false);
    };

    // Handle clicks outside the menu
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (showMenu &&
                menuRef.current &&
                buttonRef.current &&
                !menuRef.current.contains(event.target as Node) &&
                !buttonRef.current.contains(event.target as Node)) {
                setShowMenu(false);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, [showMenu]);

    return (
        <div className="relative">
            {/* Direct file input for testing */}
            {debugMode && (
                <div className="absolute bottom-full left-0 mb-20 z-50 bg-red-500 p-2 rounded">
                    <p className="text-white text-xs mb-1">Debug mode: File input below</p>
                    <input
                        type="file"
                        onChange={handleFileChange}
                        onClick={handleDirectFileInputClick}
                        multiple
                        className="text-white text-xs"
                    />
                </div>
            )}

            {/* Tooltip */}
            {showTooltip && !showMenu && (
                <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-white text-[#343541] text-xs rounded whitespace-nowrap shadow-md">
                    Upload Files
                    <div className="absolute top-full left-1/2 transform -translate-x-1/2 border-4 border-transparent border-t-white"></div>
                </div>
            )}

            {/* Upload Button (Round) */}
            <button
                ref={buttonRef}
                type="button"
                onClick={handleButtonClick}
                disabled={disabled}
                onMouseEnter={() => setShowTooltip(true)}
                onMouseLeave={() => setShowTooltip(false)}
                className={`rounded-full h-10 w-10 flex items-center justify-center 
                    bg-[#565869] text-white hover:bg-[#676980]
                    ${disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}
                    transition-colors`}
                title="Upload Files"
            >
                <PlusIcon className="h-5 w-5" />
            </button>

            {/* Dropdown Menu with Rounded Container and Option */}
            {showMenu && (
                <div
                    ref={menuRef}
                    className="absolute bottom-full left-0 mb-2 bg-[#40414f] rounded-xl shadow-lg overflow-hidden z-10 whitespace-nowrap"
                >
                    <div className="py-1">
                        <div
                            className="px-4 py-3 mx-2 my-1 text-white bg-[#4a4b59] hover:bg-[#565869] cursor-pointer rounded-lg flex items-center gap-2 relative"
                            onClick={handleUploadClick}
                        >
                            <FilePlus2Icon className="h-5 w-5" />
                            <span>Upload from computer</span>

                            {/* Transparent file input overlaid on the menu item */}
                            <input
                                type="file"
                                ref={fileInputRef}
                                onChange={handleFileChange}
                                multiple
                                className="absolute inset-0 opacity-0 cursor-pointer z-10 w-full"
                                aria-label="File Upload"
                            />
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
} 